"""Offline index-only bootstrap replay. Never execution or forward validation."""
from __future__ import annotations

import argparse
from collections import Counter, deque
from contextlib import closing
from dataclasses import asdict
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .decision import shadow_decision
from .evidence_families import evidence_families, recompute_consensus
from .historical_ingestion import IST, KEYS, normalize
from .knowledge_policy import KT_VERSION
from .market import Candle
from .momentum import momentum_family, cross_index_momentum
from .replay_capture import replay_capture, engine_fingerprint
from .structure import analyze_structure

VERSION = 'historical-index-replay-v1'
MINUTE = timedelta(minutes=1)
MISSING = ['historical_option_chains', 'bid_ask_and_greeks', 'option_premium_outcomes',
           'full_evidence_replay', 'walk_forward_validation', 'cost_adjusted_trade_results',
           'historical_breadth_sectors_vix', 'prior_day_and_opening_range_context']


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(encoded(value).encode()).hexdigest()


def source_connection(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.execute('PRAGMA query_only=ON')
    db.execute('BEGIN')  # Stable SQLite read snapshot for both replay passes.
    return db


def load_session(db, day):
    result = {s: {} for s in KEYS}
    for symbol, key in KEYS.items():
        rows = db.execute('SELECT ts,payload,source FROM historical_candles '
                          'WHERE instrument_key=? AND session_date=? ORDER BY ts', (key, day))
        for ts, payload, source in rows:
            raw = json.loads(payload)
            # Ingestion stores optional OI as null; normalize accepts absent OI.
            row = normalize(raw[:6] if len(raw) == 7 and raw[6] is None else raw)
            at = datetime.fromisoformat(row[0])
            if (source != 'upstox:v3:minutes:1' or ts != row[0] or str(at.date()) != day
                    or at.second or at.microsecond or not time(9, 15) <= at.time() < time(15, 30)
                    or at in result[symbol]):
                raise ValueError('Invalid source identity, session, cadence or duplicate')
            result[symbol][at] = dict(zip(('ts', 'open', 'high', 'low', 'close', 'volume'), row[:6]))
    return result


def aggregate(rows):
    return {'ts': rows[0]['ts'], 'open': rows[0]['open'],
            'high': max(r['high'] for r in rows), 'low': min(r['low'] for r in rows),
            'close': rows[-1]['close'], 'volume': sum(r['volume'] for r in rows)}


class ReplayClock:
    """Receives one completed minute at a time; has no source/store/provider access."""
    def __init__(self):
        self.buffers = {s: {n: deque(maxlen=60) for n in (1, 5, 15)} for s in KEYS}
        self.last = None

    def advance(self, start, rows):
        if start.tzinfo is None or start.second or start.microsecond:
            raise ValueError('Expected aware minute start')
        start = start.astimezone(IST)
        if self.last is not None and start <= self.last:
            raise ValueError('Replay clock must advance strictly')
        reset = self.last is None or start.date() != self.last.date() or start-self.last != MINUTE
        self.last = start
        structures, momentum, windows = {}, {}, {}
        for symbol in KEYS:
            buffer = self.buffers[symbol]
            row = rows.get(symbol)
            if reset or row is None:
                for values in buffer.values():
                    values.clear()
            if row is not None:
                if datetime.fromisoformat(row['ts']) != start:
                    raise ValueError('Future or mismatched input bar')
                buffer[1].append(dict(row))
                elapsed = start.hour*60 + start.minute - 555 + 1
                for n in (5, 15):
                    if elapsed % n == 0 and len(buffer[1]) >= n:
                        buffer[n].append(aggregate(list(buffer[1])[-n:]))
            windows[symbol] = {str(n): list(values) for n, values in buffer.items()}
            structures[symbol] = {}
            for n, values in buffer.items():
                structures[symbol][str(n)] = (asdict(analyze_structure([
                    Candle(symbol=symbol, timestamp=datetime.fromisoformat(r['ts']),
                           interval=f'{n}m', **{k: r[k] for k in ('open', 'high', 'low', 'close', 'volume')})
                    for r in values])) if len(values) >= 21 else {'status': 'WARMUP'})
            momentum[symbol] = momentum_family(list(buffer[1]))
        # Preserve family independence; 5m/15m are context, not extra votes.
        contexts = {s: {'status': 'OK', 'trend': structures[s]['1']['trend'].upper()}
                    if 'trend' in structures[s]['1'] else None for s in KEYS}
        families = evidence_families({}, {}, contexts['NIFTY'], contexts['BANKNIFTY'])['families']
        families['momentum_velocity'] = cross_index_momentum(momentum['NIFTY'], momentum['BANKNIFTY'])
        for name in ('options_response', 'cross_index', 'breadth', 'sector_leadership',
                     'volatility', 'derivatives_positioning'):
            families[name] = {'state': 'UNAVAILABLE', 'ce': 0, 'pe': 0}
        consensus = {**recompute_consensus(families), 'families': families}
        decision = shadow_decision(consensus, {'live_evidence_ready': False}, {})
        decision.update(operator_action='WAIT', calibrated_probability=None, probability=None,
                        calibration_eligible=False, live_evidence_eligible=False,
                        reason='Historical index-only evidence; required option/live evidence unavailable')
        known_at = start + MINUTE
        capture = replay_capture(options={}, structures=structures, families=consensus,
                                 kind='historical_bootstrap', captured_at=known_at)
        capture.update(windows=windows, momentum=momentum, missing_capabilities=MISSING,
                       limitations=['Index OHLC only; no option prices, fills or intrabar ordering.',
                                    'Session-local 60-bar windows; warmup resets on missing minutes.',
                                    'Overlapping observations are not independent trades.'])
        return {'version': VERSION, 'kt_version': KT_VERSION, 'known_at': known_at.isoformat(),
                'bar_start': start.isoformat(), 'evidence_partition': 'historical_bootstrap',
                'decision': decision, 'capture': capture}


def label_index_path(record, symbol, rows, horizon):
    """Fixed horizon underlying movement, explicitly not an option trade label."""
    at = datetime.fromisoformat(record['known_at'])
    current = record['capture']['windows'][symbol]['1']
    state = record['capture']['momentum'][symbol]['state']
    result = {'kind': 'INDEX_FORWARD_MOVE', 'horizon_minutes': horizon,
              'calibration_eligible': False, 'trade_outcome_eligible': False,
              'component_direction': state}
    if not current:
        return {**result, 'status': 'MISSING_REFERENCE'}
    end = datetime.combine(at.date(), time(15, 30), IST)
    if at + horizon*MINUTE > end:
        return {**result, 'status': 'CENSORED_SESSION_END'}
    future = [rows.get(at+i*MINUTE) for i in range(horizon)]
    if any(r is None for r in future):
        return {**result, 'status': 'CENSORED_MISSING_MINUTES'}
    reference = current[-1]['close']
    delta = future[-1]['close']-reference
    return {**result, 'status': 'COMPLETE', 'reference_close': reference,
            'end_at': (at+horizon*MINUTE).isoformat(), 'observations': horizon,
            'delta_points': delta, 'return_bps': delta/reference*10000,
            'max_up_points': max(r['high'] for r in future)-reference,
            'max_down_points': min(r['low'] for r in future)-reference,
            'direction_label': 'UP' if delta > 0 else 'DOWN' if delta < 0 else 'FLAT',
            'direction_agrees': (delta > 0 if state == 'CE' else delta < 0) if state in {'CE', 'PE'} else None}


def new_store(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation rejects archives, backups, live DBs, symlinks and previous runs.
    with path.open('xb'):
        pass
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
        CREATE TABLE replay_events(id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE replay_decisions(id INTEGER PRIMARY KEY, known_at TEXT NOT NULL UNIQUE,
            payload TEXT NOT NULL, sha256 TEXT NOT NULL, previous_sha256 TEXT NOT NULL);
        CREATE TABLE replay_labels(decision_id INTEGER REFERENCES replay_decisions(id),
            symbol TEXT NOT NULL, payload TEXT NOT NULL, prediction_sha256 TEXT NOT NULL,
            PRIMARY KEY(decision_id,symbol));
    ''')
    for table in ('replay_events', 'replay_decisions', 'replay_labels'):
        for action in ('UPDATE', 'DELETE'):
            db.execute(f'CREATE TRIGGER immutable_{table}_{action} BEFORE {action} ON {table} '
                       "BEGIN SELECT RAISE(ABORT, 'Replay audit records are immutable'); END")
    return db


def run(source, output, *, horizon=15, start_date=None, end_date=None):
    if not isinstance(horizon, int) or isinstance(horizon, bool) or not 1 <= horizon <= 375:
        raise ValueError('Horizon must be 1..375 minutes')
    if start_date and end_date and start_date > end_date:
        raise ValueError('Invalid date range')
    with closing(source_connection(source)) as src:
        days = [r[0] for r in src.execute('SELECT DISTINCT session_date FROM historical_candles '
                                        'ORDER BY session_date')
                if (start_date is None or r[0] >= str(start_date))
                and (end_date is None or r[0] <= str(end_date))]
        if not days:
            raise ValueError('No source sessions selected')
        with closing(new_store(output)) as db:
            metadata = {'event': 'STARTED', 'version': VERSION, 'kt_version': KT_VERSION,
                        'source': str(Path(source).resolve()), 'horizon_minutes': horizon,
                        'engine_source_sha256': engine_fingerprint(), 'sessions': days,
                        'evidence_partition': 'historical_bootstrap', 'calibrated_probability': None,
                        'calibration_eligible': False, 'execution_enabled': False,
                        'missing_capabilities': MISSING}
            db.execute('INSERT INTO replay_events(payload) VALUES(?)', (encoded(metadata),))
            db.commit()
            coverage, counts, label_counts = [], Counter(), Counter()
            chain = '0'*64
            source_hash = sha256()
            try:
                for day in days:
                    indices = load_session(src, day)
                    source_hash.update(encoded(indices_as_rows(indices)).encode())
                    coverage.append({'date': day, 'symbols': {
                        s: {'accepted_minutes': len(rows), 'missing_minutes': 375-len(rows),
                            'complete': len(rows) == 375} for s, rows in indices.items()}})
                    clock = ReplayClock()
                    opening = datetime.combine(date.fromisoformat(day), time(9, 15), IST)
                    first_id = None
                    for i in range(375):
                        at = opening+i*MINUTE
                        record = clock.advance(at, {s: rows.get(at) for s, rows in indices.items()})
                        value = digest({'previous': chain, 'record': record})
                        cur = db.execute('INSERT INTO replay_decisions(known_at,payload,sha256,previous_sha256) '
                                         'VALUES(?,?,?,?)', (record['known_at'], encoded(record), value, chain))
                        if first_id is None:
                            first_id = cur.lastrowid
                        chain = value
                        counts[record['decision']['status']] += 1
                    # Durably freeze the entire session before the outcome evaluator runs.
                    db.commit()
                    frozen = db.execute('SELECT id,payload,sha256 FROM replay_decisions WHERE id>=? ORDER BY id',
                                        (first_id,)).fetchall()
                    for rid, payload, prediction_hash in frozen:
                        record = json.loads(payload)
                        for symbol in KEYS:
                            label = label_index_path(record, symbol, indices[symbol], horizon)
                            db.execute('INSERT INTO replay_labels VALUES(?,?,?,?)',
                                       (rid, symbol, encoded(label), prediction_hash))
                            label_counts[label['status']] += 1
                    db.commit()
                report = {**metadata, 'event': 'FINISHED', 'status': 'COMPLETE', 'coverage': coverage,
                          'complete_index_sessions': sum(all(s['complete'] for s in c['symbols'].values())
                                                         for c in coverage),
                          'decision_counts': dict(counts), 'label_counts': dict(label_counts),
                          'decision_chain_sha256': chain, 'source_rows_sha256': source_hash.hexdigest()}
                if report['complete_index_sessions'] != len(days):
                    report['status'] = 'PARTIAL'
                db.execute('INSERT INTO replay_events(payload) VALUES(?)', (encoded(report),))
                db.commit()
                return report
            except Exception as exc:
                db.rollback()
                db.execute('INSERT INTO replay_events(payload) VALUES(?)',
                           (encoded({'event': 'FAILED', 'error': type(exc).__name__}),))
                db.commit()
                raise


def indices_as_rows(indices):
    return {s: list(rows.values()) for s, rows in indices.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New separate database; must not exist')
    parser.add_argument('--horizon-minutes', type=int, default=15)
    parser.add_argument('--start-date', type=date.fromisoformat)
    parser.add_argument('--end-date', type=date.fromisoformat)
    args = parser.parse_args(argv)
    report = run(args.source, args.output, horizon=args.horizon_minutes,
                 start_date=args.start_date, end_date=args.end_date)
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
