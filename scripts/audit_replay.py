"""Chronological input-readiness audit, NOT a strategy backtest or calibration."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'services/engine'))
from dantex.decision import shadow_decision


def audit(root, manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    indices = {}
    sources = {}
    for symbol in ('NIFTY','BANKNIFTY'):
        path = Path(manifest['index_archive'])/f'{symbol}-1minute.csv'
        sources[symbol] = {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        with path.open(newline='') as f:
            rows = list(csv.DictReader(f))
        indexed = {r['timestamp_IST']:r for r in rows}
        if len(rows) != len(indexed):
            raise ValueError('Duplicate underlying timestamps')
        indices[symbol] = indexed
    selected = defaultdict(list)
    for item in manifest['selections']:
        if item['status']=='SELECTED':
            selected[item['day']].append(item)
    identity = manifest_path.stem.removeprefix('manifest-')
    output = root/f'replay-input-audit-{identity}.jsonl.gz'
    totals = Counter()
    sessions = []
    db = sqlite3.connect((root/'options.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    with gzip.open(output,'wt',encoding='utf-8') as f:
        for day in manifest['sessions']:
            contracts = {}
            for item in selected[day]:
                key = item['instrument_key']
                rows = db.execute('SELECT ts,payload FROM candles WHERE instrument_key=? AND ts>=? AND ts<?',
                                  (key,day,day+'T99')).fetchall()
                contracts[key] = {ts:json.loads(payload) for ts,payload in rows}
            stamps = sorted(set(ts for index in indices.values() for ts in index if ts[:10]==day))
            daily = Counter()
            for ts in stamps:
                available = sum(ts in observations for observations in contracts.values())
                blockers = ['HISTORICAL_BID_ASK_UNAVAILABLE','HISTORICAL_GREEKS_UNAVAILABLE',
                            'FULL_EVIDENCE_PIPELINE_NOT_RECONSTRUCTED']
                if available != 12:
                    blockers.append('SELECTED_OPTION_CANDLE_GAP')
                if not all(ts in index for index in indices.values()):
                    blockers.append('UNDERLYING_CANDLE_GAP')
                # Do not invent family consensus, option quality, spreads, or freshness.
                # This exercises the actual fail-closed decision gate, not a proxy strategy.
                decision = shadow_decision({}, {'live_evidence_ready':False}, {})
                if decision.get('authorization') != 'NONE' or decision.get('status') != 'NO_SETUP':
                    raise AssertionError('Archive inputs unexpectedly authorized a setup')
                record = {'candle_timestamp':ts,
                          'known_at':(datetime.fromisoformat(ts)+timedelta(minutes=1)).isoformat(),
                          'available_selected_option_candles':available,
                          'input_blockers':blockers,'decision_gate_result':decision,
                          'outcome':None,'probability':None}
                f.write(json.dumps(record,separators=(',',':'))+'\n')
                daily['minute_checks'] += 1
                daily['all_selected_option_candles_present'] += available==12
                daily['blocked_decisions'] += 1
            sessions.append({'day':day,**daily})
            totals.update(daily)
    db.close()
    report = {'kind':'CHRONOLOGICAL_INPUT_READINESS_AUDIT_NOT_BACKTEST',
              'source_manifest':manifest_path.name,'index_sources':sources,
              'session_count':len(sessions),'totals':dict(totals),'sessions':sessions,
              'records':output.name,'full_strategy_replay_complete':False,
              'labelled_signals':0,'probability':None,'calibration_publishable':False,
              'interpretation':'Blocked decisions reflect missing replay inputs, not absence of market opportunities.',
              'next_requirement':'Point-in-time spreads, Greeks, complete evidence, and an equivalent replay adapter.',
              'year_extension':'Deferred until the 90-session full-strategy replay prerequisites are resolved.'}
    (root/f'replay-input-audit-{identity}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sessions','index_sources')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',required=True,type=Path)
    p.add_argument('--manifest',required=True,type=Path)
    args=p.parse_args()
    audit(args.archive,args.manifest)
