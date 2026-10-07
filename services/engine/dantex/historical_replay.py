"""Offline index-only replay. No live recorder, credentials, tuning or execution."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

from .decision import shadow_decision
from .historical_ingestion import IST, KEYS, normalize
from .knowledge_policy import KT_VERSION
from .market import Candle
from .momentum import momentum_family
from .structure import analyze_structure

VERSION = "index-replay-v1"
HORIZONS = (5, 15, 30)
COST_BPS = (0, 2, 5)
MISSING = ("option_contract_prices", "bid_ask_and_greeks", "breadth",
           "sector_leadership", "volatility", "point_in_time_revision_history")


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_archive(path: Path):
    """Read only; reject mixed stores and quarantine incomplete paired sessions."""
    sessions = defaultdict(lambda: defaultdict(list))
    rejected = defaultdict(list)
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('archive integrity failed')
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='validation_samples'").fetchone():
            raise ValueError('historical and forward evidence must be separate')
        for key, ts, day, payload, source in db.execute(
                'SELECT instrument_key,ts,session_date,payload,source FROM historical_candles ORDER BY ts,instrument_key'):
            try:
                if key not in KEYS.values() or source != 'upstox:v3:minutes:1':
                    raise ValueError('unrecognized identity or source')
                raw = json.loads(payload)
                # Normalized six-field source rows have a nullable seventh OI field.
                row = normalize(raw[:6] if len(raw) == 7 and raw[6] is None else raw)
                if row[0] != ts or row[0][:10] != day:
                    raise ValueError('timestamp metadata mismatch')
                sessions[day][key].append(row)
            except (ValueError, TypeError, KeyError, OverflowError):
                rejected[day].append('invalid row or provenance')
        # Retained conflicts/invalid rows must not disappear through normalization.
        for (payload,) in db.execute('SELECT payload FROM historical_import_events ORDER BY id'):
            event = json.loads(payload)
            if event.get('event') == 'SESSION' and event.get('status') != 'COMPLETE_REGULAR_SESSION':
                rejected[event['date']].append('archive contains non-complete ingestion event')
    accepted = {}
    for day, instruments in sorted(sessions.items()):
        start = datetime.fromisoformat(day).replace(hour=9, minute=15, tzinfo=IST)
        expected = [(start + timedelta(minutes=i)).isoformat() for i in range(375)]
        if any([r[0] for r in instruments.get(key, [])] != expected for key in KEYS.values()):
            rejected[day].append('paired regular-session coverage incomplete')
        if day not in rejected:
            accepted[day] = dict(instruments)
    return accepted, {day: sorted(set(reasons)) for day, reasons in sorted(rejected.items())}


def decide(symbol: str, prefix: list[list], as_of: datetime) -> dict:
    """Only closed current-session bars are passed across the decision boundary."""
    if not prefix or as_of.tzinfo is None:
        raise ValueError('closed prefix and aware as-of time required')
    stamps = [datetime.fromisoformat(row[0]) for row in prefix]
    if any(t.tzinfo is None or t + timedelta(minutes=1) > as_of for t in stamps):
        raise ValueError('unclosed/future candle at decision boundary')
    if any(b - a != timedelta(minutes=1) for a, b in zip(stamps, stamps[1:])):
        raise ValueError('prefix must be contiguous and ordered')
    if any(t.astimezone(IST).date() != stamps[0].astimezone(IST).date() for t in stamps):
        raise ValueError('session carryover forbidden')
    candles = [Candle(symbol=symbol, timestamp=t, interval='1m', open=r[1],
                      high=r[2], low=r[3], close=r[4], volume=r[5]) for t, r in zip(stamps, prefix)]
    structure = asdict(analyze_structure(candles)) if len(candles) >= 21 else None
    momentum = momentum_family([c.model_dump() for c in candles])
    # Do not fabricate missing independent evidence or executable option contracts.
    decision = shadow_decision({}, {'live_evidence_ready': False}, {})
    return {'symbol': symbol, 'as_of': as_of.isoformat(), 'source_last_bar': prefix[-1][0],
            'closed_bars': len(prefix), 'structure': structure, 'momentum': momentum,
            'decision': decision, 'missing_evidence': list(MISSING),
            'mode': 'shadow', 'evidence_origin': 'historical_index',
            'live_evidence_eligible': False, 'calibration_ready': False, 'probability': None}


def forward_label(decision: dict, future: list[list], horizon: int) -> dict:
    """Separate evaluator: next-bar-open reference, never a trade/option fill."""
    if horizon not in HORIZONS:
        raise ValueError('unsupported fixed horizon')
    result = {'horizon_minutes': horizon, 'status': 'CENSORED',
              'reference': 'next_index_bar_open', 'trade_outcome': False}
    if len(future) < horizon:
        return result
    rows = future[:horizon]
    as_of = datetime.fromisoformat(decision['as_of'])
    stamps = [datetime.fromisoformat(r[0]) for r in rows]
    if any(t != as_of + timedelta(minutes=i) for i, t in enumerate(stamps)):
        raise ValueError('future label rows must start strictly after the decision bar')
    if any(t.astimezone(IST).date() != as_of.astimezone(IST).date() for t in stamps):
        return result
    entry, exit_price = rows[0][1], rows[-1][4]
    movement = (exit_price / entry - 1) * 10_000
    result.update(status='OBSERVED', available_at=(stamps[-1] + timedelta(minutes=1)).isoformat(),
                  entry_reference=entry, exit_reference=exit_price,
                  index_move_bps=round(movement, 6),
                  upside_bps=round((max(r[2] for r in rows) / entry - 1) * 10_000, 6),
                  downside_bps=round((min(r[3] for r in rows) / entry - 1) * 10_000, 6))
    # Frozen existing structure direction, used only as a descriptive cohort.
    trend = (decision.get('structure') or {}).get('trend')
    sign = 1 if trend == 'bullish' else -1 if trend == 'bearish' else 0
    result['directional_proxy_bps'] = round(sign * movement, 6) if sign else None
    result['hypothetical_round_trip_cost_bps'] = {
        str(cost): round(sign * movement - cost, 6) if sign else None for cost in COST_BPS}
    return result


def temporal_blocks(days: list[str]) -> dict[str, str]:
    """Fixed 30-session development / 20-session forward blocks; no fitting."""
    return {day: 'development' if i < 30 else f'holdout_{1 + (i - 30) // 20}'
            for i, day in enumerate(days)}


def run_replay(archive: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError('choose a new output directory to preserve prior evidence')
    before = digest(archive)
    sessions, rejected = load_archive(archive)
    if not sessions:
        raise ValueError('no complete paired sessions')
    output.mkdir(parents=True)
    blocks = temporal_blocks(sorted(sessions))
    counts = Counter()
    aggregates = defaultdict(lambda: {'observed': 0, 'censored': 0, 'directional': 0, 'sum_proxy_bps': 0.0})
    per_day = defaultdict(list)
    with gzip.open(output / 'decisions.jsonl.gz', 'wt', encoding='utf-8') as decisions, gzip.open(
            output / 'outcomes.jsonl.gz', 'wt', encoding='utf-8') as outcomes:
        for day, instruments in sessions.items():
            for i in range(375):
                # Synchronize both instruments at the same closed-bar cutoff.
                for symbol, key in KEYS.items():
                    rows = instruments[key]
                    as_of = datetime.fromisoformat(rows[i][0]) + timedelta(minutes=1)
                    event = decide(symbol, rows[:i+1], as_of)
                    event_id = f'{symbol}:{rows[i][0]}'
                    event.update(id=event_id, block=blocks[day])
                    decisions.write(json.dumps(event, sort_keys=True) + '\n')
                    counts[event['decision']['status']] += 1
                    for horizon in HORIZONS:
                        label = forward_label(event, rows[i+1:], horizon)
                        label.update(decision_id=event_id, block=blocks[day], symbol=symbol)
                        outcomes.write(json.dumps(label, sort_keys=True) + '\n')
                        group = f'{blocks[day]}:{symbol}:{horizon}m'
                        agg = aggregates[group]
                        agg[label['status'].lower()] += 1
                        proxy = label.get('directional_proxy_bps')
                        if proxy is not None:
                            agg['directional'] += 1
                            agg['sum_proxy_bps'] += proxy
                            per_day[(group, day)].append(proxy)
    after = digest(archive)
    if after != before:
        raise ValueError('source archive changed during replay; outputs are invalid')
    summary = {}
    for group, agg in sorted(aggregates.items()):
        daily_means = [sum(values)/len(values) for (g, _), values in per_day.items() if g == group]
        summary[group] = {**agg, 'sessions_with_directional_observations': len(daily_means),
                          'equal_session_mean_proxy_bps': round(sum(daily_means)/len(daily_means), 6) if daily_means else None,
                          'cost_sensitivity_bps': {str(c): round(sum(daily_means)/len(daily_means)-c, 6) if daily_means else None for c in COST_BPS}}
    report = {'version': VERSION, 'kt_version': KT_VERSION, 'mode': 'shadow',
              'scope': 'INDEX_ONLY_DESCRIPTIVE_REPLAY', 'status': 'COMPLETE' if not rejected else 'PARTIAL',
              'source_sha256': before, 'source_unchanged': True,
              'sessions': len(sessions), 'first_session': min(sessions), 'last_session': max(sessions),
              'quarantined_sessions': rejected, 'session_blocks': blocks,
              'decision_counts': dict(counts), 'summary': summary,
              'calibration_ready': False, 'live_evidence_eligible': False, 'probability': None,
              'missing_capabilities': list(MISSING),
              'limitations': ['All setups rejected; labels describe index movement, not executed trades.',
                             'Overlapping horizons are dependent; session means are not independent trade samples.',
                             'Holdouts are chronological engineering checks, not validated OOS profitability.',
                             'No fitting, tuning, self-adaptation or probability estimation.',
                             'Archive is downloaded history, not certified contemporaneous point-in-time data.',
                             '0/2/5 bps are hypothetical round-trip index cost sensitivities, not option costs.',
                             'OHLC does not establish intrabar target/stop order; no such labels are inferred.'],
              'artifacts': {p.name: digest(p) for p in output.glob('*.gz')}}
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    report = run_replay(args.db, args.output)
    print(json.dumps({k: report[k] for k in ('status', 'sessions', 'decision_counts', 'calibration_ready')}))
    return 0 if report['status'] == 'COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
