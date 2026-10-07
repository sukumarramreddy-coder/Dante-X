"""Replay persisted directional and four-way projections without modifying evidence."""
import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services' / 'engine'))
from dantex.expert_engine import four_way
from dantex.probability import evidence_prior


def verify(path):
    counts = Counter()
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        for rid, at, state, raw, decision in db.execute(
            'SELECT id,recorded_at,state,market_snapshot,decision FROM validation_samples ORDER BY id'
        ):
            if at[:10] not in {'2026-09-30', '2026-10-01'}:
                continue
            counts['records'] += 1
            snapshot = json.loads(raw or 'null') or {}
            stored = json.loads(decision or 'null') or {}
            if state == 'EXPERT_REVIEW':
                actual = four_way(snapshot)
                assert actual == stored['expert_review']['deterministic'], f'four-way mismatch {rid}'
                counts['four_way_replays'] += 1
            families = (snapshot.get('replay') or {}).get('evidence_families') or {}
            if stored.get('probability_review') and families:
                actual = evidence_prior(families, families.get('readiness') or {})
                assert actual['directional'] == stored['probability_review']['directional'], f'probability mismatch {rid}'
                assert actual['authorization'] == 'NONE' and not actual['calibrated']
                counts['directional_replays'] += 1
    return dict(counts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', help='Existing validation SQLite database (opened read-only)')
    print(json.dumps(verify(parser.parse_args().database), indent=2))
