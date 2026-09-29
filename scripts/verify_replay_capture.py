"""One read-only provider check, saved in a separate local diagnostic database."""
import json
import os
from pathlib import Path
import sys

from archive_options import load_token

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'local-data/recorder-check'
OUT.mkdir(parents=True, exist_ok=True)
os.environ['UPSTOX_ANALYTICS_TOKEN'] = load_token(ROOT/'.env')
os.environ['DANTEX_MODE'] = 'shadow'
os.environ['DANTEX_VALIDATION_DB'] = str(OUT/'observations.sqlite3')
# This diagnostic must never send test observations to an external evidence sink.
os.environ['DANTEX_VALIDATION_REST_URL'] = ''
os.environ['DANTEX_VALIDATION_REST_KEY'] = ''
sys.path.insert(0, str(ROOT/'services/engine'))

from dantex.api import evaluate_option_duel
from dantex.providers.upstox_master import instrument_master
from dantex.validation_recorder import validation_recorder


def main():
    instrument_master._refresh()
    result = evaluate_option_duel()
    record = validation_recorder.recent(1)[0]
    captured = record['market_snapshot']['replay']
    fields = ('instrument_key','ltp','bid_price','ask_price','bid_qty','ask_qty',
              'volume','oi','prev_oi','iv','delta','gamma','theta','vega')
    coverage = {}
    for symbol, snapshot in captured['options'].items():
        legs = [row.get(side) or {} for row in snapshot.get('strikes',[]) for side in ('call','put')]
        coverage[symbol] = {'status':snapshot.get('status'),'legs':len(legs),
            'fields_present':{field:sum(leg.get(field) is not None for leg in legs) for field in fields},
            'source':snapshot.get('source')}
    summary = {'kind':'READ_ONLY_OFFLINE_DIAGNOSTIC', 'sample_id':record['id'],
        'recorded_at':record['recorded_at'],'schema':captured['schema_version'],
        'engine_source_sha256':captured['engine_source_sha256'],
        'options':coverage,'quote_input_groups':list(captured['quote_inputs']),
        'structure_groups':list(captured['structures']),
        'decision':result.get('decision'),'market_state':record['state'],
        'capture_bytes':len(json.dumps(captured).encode()),
        'calibration_eligible':False,'external_evidence_written':False,
        'note':'Single current-context check, not proof of a full live session or deployment.'}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status':'CHECK_FAILED','error_type':type(exc).__name__}))
        raise SystemExit(2) from None
