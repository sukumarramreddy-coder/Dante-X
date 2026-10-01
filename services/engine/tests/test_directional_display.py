import json
from pathlib import Path

from dantex.decision import shadow_decision
from dantex.expert_engine import four_way


def test_stored_directional_sessions_preserve_probability_and_authorization():
    rows = json.loads((Path(__file__).parent / 'fixtures/directional_sessions.json').read_text())
    assert {row['at'][:10] for row in rows} == {'2026-09-30', '2026-10-01'}
    for row in rows:
        result = shadow_decision(row['families'], row['readiness'], {})
        assert result['authorization'] == 'NONE'  # No contract input in this projection.
        assert result['auto_execution'] is False
        assert result['probability_review']['directional'] == row['decision']['probability_review']['directional']
        assert result['probability_review']['calibrated'] is False
        stale = shadow_decision(row['families'], {'live_evidence_ready': False}, {})
        assert stale['authorization'] == 'NONE'
        assert stale['probability_review']['status'] == 'PRIOR_ONLY'
        assert stale['probability_review']['data_quality'] == 'STALE_OR_MISSING'


def test_stored_oct1_four_way_downside_to_late_ce_preference_remains_blocked():
    rows = json.loads((Path(__file__).parent / 'fixtures/expert_sessions.json').read_text())
    for row in rows:
        result = four_way(row['snapshot'])
        assert result == row['expected']
        assert result['best_candidate'] is None
        assert all('validated_structural_plan' in c['missing_data'] for c in result['candidates'])
    late = four_way(rows[-1]['snapshot'])['candidates']
    assert four_way(rows[0]['snapshot'])['regimes']['NIFTY']['regime'] == 'TREND_DOWN'
    assert four_way(rows[1]['snapshot'])['regimes']['NIFTY']['reversal'] == 'CE'
    nifty = {c['side']: c['directional_score'] for c in late if c['instrument'] == 'NIFTY'}
    assert nifty['CE'] > nifty['PE']
