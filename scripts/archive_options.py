"""Read-only, resumable option-candle archive. Never writes live evidence or calibrations."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import sqlite3
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

IST = ZoneInfo('Asia/Kolkata')
KEYS = {'NIFTY': 'NSE_INDEX|Nifty 50', 'BANKNIFTY': 'NSE_INDEX|Nifty Bank'}
POLICY = 'previous-close-nearest-expiry-atm-plus-minus-one-v1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def validate_candles(rows, start, end):
    """Retain first observation, quarantine conflicting timestamps, never fill gaps."""
    accepted, conflicts = {}, set()
    counts = defaultdict(int)
    for raw in rows:
        try:
            if not isinstance(raw, list) or len(raw) != 7:
                raise ValueError('shape')
            stamp = datetime.fromisoformat(raw[0])
            if stamp.tzinfo is None:
                raise ValueError('timezone')
            stamp = stamp.astimezone(IST)
            if not start <= stamp.date().isoformat() <= end or stamp.second or stamp.microsecond:
                raise ValueError('date or interval')
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                       and math.isfinite(v) for v in raw[1:]):
                raise ValueError('numeric')
            o, h, l, c, volume, oi = raw[1:]
            if min(o, h, l, c) <= 0 or not l <= min(o, c) <= max(o, c) <= h:
                raise ValueError('prices')
            if volume < 0 or oi < 0:
                raise ValueError('volume')
            if not 555 <= stamp.hour * 60 + stamp.minute < 930:
                counts['outside_regular_hours'] += 1
                continue
            row = [stamp.isoformat(), *map(float, raw[1:])]
            ts = row[0]
            if ts in accepted:
                counts['duplicate_rows'] += 1
                if accepted[ts] != row:
                    conflicts.add(ts)
            else:
                accepted[ts] = row
        except (ValueError, TypeError, OverflowError):
            counts['invalid_rows'] += 1
    for ts in conflicts:
        accepted.pop(ts, None)
    counts['conflicting_timestamps'] = len(conflicts)
    return sorted(accepted.values()), dict(counts)


def select_contracts(contracts, previous_close):
    """Frozen daily research universe, not a recreation of live contract ranking."""
    strikes = sorted({float(c['strike_price']) for c in contracts
                      if c.get('instrument_type') in ('CE', 'PE')})
    if not strikes:
        return []
    middle = min(range(len(strikes)), key=lambda i: (abs(strikes[i]-previous_close), strikes[i]))
    chosen = set(strikes[max(0, middle-1):middle+2])
    selected = [c for c in contracts if float(c['strike_price']) in chosen
                and c.get('instrument_type') in ('CE', 'PE')]
    identities = [(float(c['strike_price']), c['instrument_type']) for c in selected]
    if len(identities) != len(set(identities)):
        raise ValueError('Ambiguous contract metadata')
    return sorted(selected, key=lambda c: (float(c['strike_price']), c['instrument_type']))


class Archive:
    def __init__(self, root, token):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root/'raw').mkdir(exist_ok=True)
        self.token = token
        self.last_request = 0.0
        self.db = sqlite3.connect(self.root/'options.sqlite3')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS candles (
              instrument_key TEXT, ts TEXT, payload TEXT, source_request TEXT,
              PRIMARY KEY(instrument_key,ts));
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY, recorded_at TEXT, kind TEXT, payload TEXT);
        ''')

    def event(self, kind, payload):
        with self.db:
            self.db.execute('INSERT INTO events(recorded_at,kind,payload) VALUES(?,?,?)',
                            (datetime.now(IST).isoformat(), kind, canonical(payload)))

    def get(self, path):
        if not path.startswith(('/v2/expired-instruments/', '/v2/option/contract?',
                                '/v3/historical-candle/')):
            raise ValueError('Only historical market-data endpoints are permitted')
        digest = hashlib.sha256(path.encode()).hexdigest()
        cache = self.root/'raw'/f'{digest}.json.gz'
        if cache.exists():
            with gzip.open(cache, 'rt', encoding='utf-8') as f:
                saved = json.load(f)
            if saved['request_path'] != path:
                raise ValueError('Cache identity mismatch')
            return saved['response'], digest
        for attempt in range(4):
            time.sleep(max(0, 0.45-(time.monotonic()-self.last_request)))
            self.last_request = time.monotonic()
            try:
                req = Request('https://api.upstox.com'+path, headers={
                    'Accept': 'application/json', 'User-Agent': 'Dante-X/0.1',
                    'Authorization': 'Bearer '+self.token})
                with urlopen(req, timeout=25) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict) or payload.get('status') != 'success':
                    raise ValueError('Unsuccessful provider payload')
                saved = {'request_path': path, 'retrieved_at': datetime.now(IST).isoformat(),
                         'response': payload}
                temporary = cache.with_suffix('.tmp')
                with gzip.open(temporary, 'wt', encoding='utf-8') as f:
                    json.dump(saved, f)
                temporary.replace(cache)
                return payload, digest
            except HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 3:
                    raise RuntimeError(f'Provider HTTP {exc.code}') from None
            except (URLError, TimeoutError):
                if attempt == 3:
                    raise RuntimeError('Provider connection failed') from None
            time.sleep(2**attempt)
        raise RuntimeError('Provider retries exhausted')

    def candles(self, contract, start, end):
        key = contract['instrument_key']
        escaped = quote(key, safe='')
        if len(key.split('|')) >= 3:
            path = f'/v2/expired-instruments/historical-candle/{escaped}/1minute/{end}/{start}'
        else:
            path = f'/v3/historical-candle/{escaped}/minutes/1/{end}/{start}'
        payload, request_id = self.get(path)
        raw = payload.get('data', {}).get('candles')
        if not isinstance(raw, list):
            raise ValueError('Missing candle array')
        rows, quality = validate_candles(raw, start, end)
        stored_conflicts = 0
        with self.db:
            for row in rows:
                value = canonical(row)
                old = self.db.execute('SELECT payload FROM candles WHERE instrument_key=? AND ts=?',
                                      (key, row[0])).fetchone()
                if old:
                    stored_conflicts += old[0] != value
                else:
                    self.db.execute('INSERT INTO candles VALUES(?,?,?,?)',
                                    (key, row[0], value, request_id))
        quality.update(raw_rows=len(raw), accepted_rows=len(rows), stored_conflicts=stored_conflicts)
        self.event('FETCH_VALIDATED', {'key': key, 'start': start, 'end': end, **quality})
        return rows, quality


def load_token(env):
    values = {}
    for line in Path(env).read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    token = values.get('UPSTOX_ANALYTICS_TOKEN')
    if not token:
        raise ValueError('Read-only Analytics Token is not configured')
    return token


def run(args):
    archive = Archive(args.output, load_token(args.env))
    indices = {}
    for symbol in KEYS:
        with (Path(args.index_archive)/f'{symbol}-1minute.csv').open(newline='') as f:
            indices[symbol] = list(csv.DictReader(f))
    days = sorted({r['timestamp_IST'][:10] for rows in indices.values() for r in rows})
    if not days or days[-1] >= datetime.now(IST).date().isoformat():
        raise ValueError('Only settled historical sessions are permitted')
    requested_start = (date.fromisoformat(days[0])-timedelta(days=14)).isoformat()
    selections, contracts_by_key, jobs = [], {}, defaultdict(set)
    for symbol, key in KEYS.items():
        daily, _ = archive.get(f'/v3/historical-candle/{quote(key,safe="")}/days/1/{days[-1]}/{requested_start}')
        daily_rows = daily.get('data', {}).get('candles', [])
        prior_closes = {r[0][:10]: float(r[4]) for r in daily_rows}
        # Existing archive is authoritative for its sessions; do not replace it.
        for row in sorted(indices[symbol], key=lambda r: r['timestamp_IST']):
            prior_closes[row['timestamp_IST'][:10]] = float(row['close'])
        expiries, _ = archive.get('/v2/expired-instruments/expiries?'+urlencode({'instrument_key': key}))
        expiry_dates = sorted(expiries['data'])
        if not expiry_dates or expiry_dates[-1] < days[-1]:
            live, _ = archive.get('/v2/option/contract?'+urlencode({'instrument_key': key}))
            live_contracts = live['data']
            expiry_dates = sorted(set(expiry_dates) | {c['expiry'] for c in live_contracts})
        else:
            live_contracts = []
        for day in days:
            earlier = [d for d in prior_closes if d < day]
            future = [d for d in expiry_dates if d >= day]
            if not earlier or not future:
                selections.append({'symbol':symbol,'day':day,'status':'MISSING_REFERENCE_OR_EXPIRY'})
                continue
            prior_day, expiry = max(earlier), min(future)
            if expiry in expiries['data']:
                metadata, _ = archive.get('/v2/expired-instruments/option/contract?'+urlencode(
                    {'instrument_key':key,'expiry_date':expiry}))
                contracts = metadata['data']
            else:
                contracts = [c for c in live_contracts if c['expiry'] == expiry]
            contracts = [c for c in contracts if c.get('expiry') == expiry
                         and c.get('underlying_key') == key]
            chosen = select_contracts(contracts, prior_closes[prior_day])
            if len(chosen) != 6:
                selections.append({'symbol':symbol,'day':day,'status':'INCOMPLETE_CONTRACT_SELECTION',
                                   'selected_contracts':len(chosen)})
            for contract in chosen:
                instrument = contract['instrument_key']
                contracts_by_key[instrument] = contract
                jobs[instrument].add(day)
                selections.append({'symbol':symbol,'day':day,'status':'SELECTED',
                    'prior_day':prior_day,'previous_close':prior_closes[prior_day],
                    'expiry':expiry,'instrument_key':instrument,
                    'strike':contract['strike_price'],'side':contract['instrument_type']})
        print(canonical({'event':'universe_ready','symbol':symbol,'contract_jobs':len(jobs)}),flush=True)
    manifest = {'policy':POLICY,'index_archive':str(Path(args.index_archive).resolve()),
                'sessions':days,'selections':selections,'contracts':contracts_by_key}
    identity = hashlib.sha256(canonical(manifest).encode()).hexdigest()[:16]
    (archive.root/f'manifest-{identity}.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    coverage, errors = [], []
    for number, (key, needed_days) in enumerate(sorted(jobs.items()), 1):
        # A one-month maximum window also bounds active V3 minute requests.
        remaining = sorted(needed_days)
        while remaining:
            start = remaining[0]
            limit = (date.fromisoformat(start)+timedelta(days=27)).isoformat()
            window = [d for d in remaining if d <= limit]
            remaining = [d for d in remaining if d > limit]
            end = window[-1]
            try:
                rows, quality = archive.candles(contracts_by_key[key],start,end)
                counts = defaultdict(int)
                for row in rows:
                    counts[row[0][:10]] += 1
                for day in window:
                    coverage.append({'instrument_key':key,'day':day,'regular_minutes':counts[day],
                        'missing_regular_minutes':375-counts[day],
                        'range_quality':quality,
                        'status':'COMPLETE_REGULAR_GRID' if counts[day]==375 and
                        not any(quality.get(k,0) for k in ('invalid_rows','conflicting_timestamps',
                                  'stored_conflicts','outside_regular_hours')) else 'REVIEW_REQUIRED'})
            except (RuntimeError, ValueError, TypeError) as exc:
                errors.append({'instrument_key':key,'start':start,'end':end,'error':type(exc).__name__})
                archive.event('FETCH_FAILED',errors[-1])
                # Authentication/entitlement blocks must not produce a flood of requests.
                if isinstance(exc,RuntimeError) and any(s in str(exc) for s in ('401','403')):
                    raise
        if number % 10 == 0 or number == len(jobs):
            print(canonical({'event':'progress','completed_contracts':number,'total_contracts':len(jobs),
                             'failed_windows':len(errors)}),flush=True)
    report = {'policy':POLICY,'manifest':f'manifest-{identity}.json',
        'source':'Upstox historical option candles','start':days[0],'end':days[-1],
        'sessions':len(days),'contract_jobs':len(jobs),'selected_contract_days':sum(len(v) for v in jobs.values()),
        'completed_contract_days':len(coverage),'complete_regular_grid_days':sum(c['status']=='COMPLETE_REGULAR_GRID' for c in coverage),
        'errors':errors,'selection_gaps':[s for s in selections if s['status']!='SELECTED'],
        'coverage':coverage,'stored_candles':archive.db.execute('SELECT COUNT(*) FROM candles').fetchone()[0],
        'database_integrity':archive.db.execute('PRAGMA integrity_check').fetchone()[0],
        'full_strategy_replay':'BLOCKED_MISSING_HISTORICAL_SPREADS_GREEKS_AND_FULL_EVIDENCE',
        'calibration_ready':False,'probability':None,
        'limitations':['Research universe frozen from previous close; not live contract ranking.',
          'Contract metadata is retrospective, not a point-in-time listing archive.',
          'Missing minutes may reflect no trades or missing data; no prices are forward-filled.',
          'No bid/ask, Greeks, historical order book, outcome labels, or profitability claims.',
          'If stop and target are both touched in one candle, event order is unknowable.']}
    path = archive.root/f'coverage-{identity}.json'
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    archive.event('RUN_FINISHED',{'report':path.name,'stored_candles':report['stored_candles']})
    print(canonical({k:v for k,v in report.items() if k not in ('coverage','selection_gaps','limitations')}),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env',default='.env')
    parser.add_argument('--index-archive',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    try:
        run(args)
    except Exception as exc:
        # Never print request headers, tokens, or untrusted provider bodies.
        print(canonical({'status':'BLOCKED','error_type':type(exc).__name__}),flush=True)
        raise SystemExit(2) from None


if __name__ == '__main__':
    main()
