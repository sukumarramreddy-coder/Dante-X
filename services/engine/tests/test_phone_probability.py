from datetime import datetime, timedelta

from dantex.expert_runtime import DecisionRuntime
from dantex.freshness import IST
from dantex.probability import FAMILIES
from dantex.validation_recorder import ValidationRecorder


def test_phone_review_is_additive_and_expired_review_is_neutral(tmp_path, monkeypatch):
    from dantex import expert_runtime
    now = datetime.now(IST)
    snapshot = {'snapshot_id': 'test', 'timestamp': now.isoformat(), 'missing_data': [], 'position': None,
                'indices': {symbol: {'fresh': True} for symbol in ('NIFTY', 'BANKNIFTY')}}
    monkeypatch.setattr(expert_runtime, 'normalized_snapshot', lambda *args, **kwargs: snapshot.copy())
    monkeypatch.setattr(expert_runtime, 'four_way', lambda snapshot: {
        'regimes': {}, 'four_way_reset': False, 'candidates': [], 'best_candidate': None})
    runtime = DecisionRuntime(ValidationRecorder(str(tmp_path/'validation.db')))
    result = runtime.evaluate(
        {'NIFTY': {'path_response': {'state': 'CE_STRENGTHENING'}},
         'BANKNIFTY': {'path_response': {'state': 'PE_STRENGTHENING'}}},
        {s: {'status': 'OK', 'evidence_eligible': True, 'trend': trend} for s, trend in
         [('NIFTY', 'BULLISH'), ('BANKNIFTY', 'BEARISH')]}, {'families': {name: {'state': 'CE'} for name in FAMILIES},
                                      'readiness': {'live_evidence_ready': True}})
    assert result['probability_review']['directional']['ce'] == 65
    assert result['index_probability_reviews']['NIFTY']['directional']['ce'] == 65
    assert result['index_probability_reviews']['BANKNIFTY']['directional']['ce'] == 35
    assert result['probability_review']['authorization'] == 'NONE'
    assert result['final']['action'] == 'NO_EDGE'
    assert result['final']['auto_execution'] is False
    assert result['final']['calibrated_probability'] is None
    with runtime._lock:
        runtime._current['timestamp'] = (now-timedelta(minutes=5)).isoformat()
    stale = runtime.current()
    assert stale['probability_review']['directional']['ce'] == 50
    assert stale['probability_review']['status'] == 'PRIOR_ONLY'
    assert 'stale_decision' in stale['probability_review']['blocked_sources']
    assert runtime._current['probability_review']['directional']['ce'] == 65
    for review in stale['index_probability_reviews'].values():
        assert review['directional'] == {'ce': 50.0, 'pe': 50.0}
        assert not review['fresh_evidence']
    assert runtime._current['index_probability_reviews']['NIFTY']['directional']['ce'] == 65
    restored = DecisionRuntime(runtime.recorder).current()
    assert restored['restored_from_audit'] is True
    assert restored['feed_fresh'] is False
    assert restored['final']['action'] == 'NO_EDGE'
    assert restored['probability_review']['directional']['ce'] == 50
    assert all(r['directional']['ce'] == 50 for r in restored['index_probability_reviews'].values())
    assert runtime.recorder.status()['samples'] == 1
