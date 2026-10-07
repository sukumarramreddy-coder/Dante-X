"""Causal replay of Dante's existing momentum component; no trades or win rates."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'services/engine'))
from dantex.momentum import momentum_family, cross_index_momentum
from dantex.replay_capture import engine_fingerprint


def component_records(indices):
    buffers = {s:deque(maxlen=60) for s in indices}
    last = {}
    for stamp in sorted({ts for rows in indices.values() for ts in rows}):
        at = datetime.fromisoformat(stamp)
        states = {}
        for symbol, rows in indices.items():
            row = rows.get(stamp)
            # Restart warmup after any gap or session boundary; never bridge missing bars.
            if (row is None or symbol not in last or at.date()!=last[symbol].date()
                    or at-last[symbol]!=timedelta(minutes=1)):
                buffers[symbol].clear()
            if row is not None:
                buffers[symbol].append(row)
                last[symbol] = at
            states[symbol] = momentum_family(list(buffers[symbol]))
        yield {'candle_timestamp':stamp,'known_at':(at+timedelta(minutes=1)).isoformat(),
               'momentum':states,
               'cross_index_momentum':cross_index_momentum(states['NIFTY'],states['BANKNIFTY']),
               'authorization':'NONE','probability':None}


def run(source, output):
    output.mkdir(parents=True,exist_ok=True)
    indices, sources = {}, {}
    for symbol in ('NIFTY','BANKNIFTY'):
        path=source/f'{symbol}-1minute.csv'
        sources[symbol]={'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        with path.open(newline='') as f:
            rows=list(csv.DictReader(f))
        indices[symbol]={r['timestamp_IST']:{k:float(r[k]) for k in ('open','high','low','close','volume')}
                         for r in rows}
        if len(rows)!=len(indices[symbol]):
            raise ValueError('Duplicate source timestamps')
    counts=defaultdict(Counter)
    sessions=set()
    checks=0
    with gzip.open(output/'momentum-component-replay.jsonl.gz','wt',encoding='utf-8') as f:
        for record in component_records(indices):
            checks+=1
            sessions.add(record['candle_timestamp'][:10])
            for symbol, state in record['momentum'].items():
                counts[symbol][state['state']]+=1
            counts['cross_index'][record['cross_index_momentum']['state']]+=1
            f.write(json.dumps(record,separators=(',',':'))+'\n')
    result={'kind':'CANDLE_COMPONENT_REPLAY_NOT_STRATEGY_BACKTEST',
        'engine_source_sha256':engine_fingerprint(),'sources':sources,
        'sessions':len(sessions),'timestamps':checks,'component_state_counts':dict(counts),
        'labels':0,'probability':None,'authorization':'NONE',
        'limitations':['Existing momentum component only, with its existing 60-candle input window.',
          'Minute bars are processed after close; live polling occurs at a different cadence.',
          'These overlapping state counts are not independent signals, trades or success rates.',
          'No thresholds fitted, strategy outcomes labelled, or cost-adjusted returns claimed.']}
    (output/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='sources'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index-archive',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    run(args.index_archive,args.output)
