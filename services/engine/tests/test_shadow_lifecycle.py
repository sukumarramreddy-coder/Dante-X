from datetime import datetime, timedelta

import pytest

from dantex.freshness import IST
from dantex.shadow_lifecycle import ShadowLifecycle

NOW = datetime(2026, 9, 24, 12, tzinfo=IST)


def inputs(now=NOW, price=100, direction='CE', ready=True, key='locked'):
    decision = {'status': 'DETECTED', 'direction': direction,
                'contract': {'instrument_key': 'locked', 'expiry': '2026-09-29', 'strike': 23000},
                'reference_entry': 100, 'reference_stop': 85, 'reference_t1': 120, 'reference_t2': 135}
    families = {'state': direction + '_EVIDENCE', 'readiness': {'live_evidence_ready': ready}}
    options = {'expiry': '2026-09-29', 'strikes': [{'call' if direction == 'CE' else 'put': {'instrument_key': key, 'ltp': price}}],
               'path_response': {'last_sample_at': now.isoformat(), 'state': direction + '_STRENGTHENING'}}
    return decision, families, options


@pytest.mark.parametrize('direction', ['CE', 'PE'])
def test_full_persistent_lifecycle_and_locked_levels(tmp_path, direction):
    store = ShadowLifecycle(str(tmp_path/'signals.db'))
    result = store.advance(*inputs(direction=direction), now=NOW)
    assert result['status'] == 'WAIT'
    signal_id = result['signal_id']
    for seconds, price, expected in [(10, 101, 'GO'), (20, 110, 'HOLD'), (30, 136, 'RUN'), (40, 84, 'EXIT')]:
        now = NOW + timedelta(seconds=seconds)
        args = inputs(now, price, direction)
        args[0]['reference_entry'] = 999  # New candidate cannot move the locked trigger.
        result = store.advance(*args, now=now)
        assert result['status'] == expected
        assert result['signal_id'] == signal_id
        assert result['reference_entry'] == 100
        assert result['probability'] is None
    reopened = ShadowLifecycle(store.path).snapshot()
    assert reopened['current']['status'] == 'EXIT'
    assert len(reopened['events']) == 5


@pytest.mark.parametrize('kind', ['stale', 'future', 'missing_contract', 'changed_expiry', 'duplicate', 'out_of_order'])
def test_bad_observation_never_fires_or_replaces_plan(tmp_path, kind):
    store = ShadowLifecycle(str(tmp_path/'signals.db'))
    store.advance(*inputs(), now=NOW)
    now = NOW + timedelta(seconds=10)
    decision, families, options = inputs(now, 110)
    if kind == 'stale': families['readiness']['live_evidence_ready'] = False
    if kind == 'future': options['path_response']['last_sample_at'] = (now+timedelta(days=1)).isoformat()
    if kind == 'missing_contract': options['strikes'][0]['call']['instrument_key'] = 'different'
    if kind == 'changed_expiry': options['expiry'] = '2026-10-06'
    if kind == 'duplicate': options['path_response']['last_sample_at'] = NOW.isoformat()
    if kind == 'out_of_order': options['path_response']['last_sample_at'] = (NOW-timedelta(seconds=1)).isoformat()
    result = store.advance(decision, families, options, now=now)
    assert result['status'] == 'WAIT'
    assert result['authorization'] == 'NONE'
    assert store.snapshot()['current']['reference_entry'] == 100
    assert len(store.snapshot()['events']) == 1


def test_conflict_cancels_wait_and_warns_open_plan(tmp_path):
    store = ShadowLifecycle(str(tmp_path/'signals.db'))
    store.advance(*inputs(), now=NOW)
    now = NOW + timedelta(seconds=10)
    args = inputs(now)
    args[1]['state'] = 'CONFLICT'
    assert store.advance(*args, now=now)['status'] == 'CANCEL'
    now += timedelta(seconds=10)
    assert store.advance(*inputs(now), now=now)['status'] == 'WAIT'
    now += timedelta(seconds=10)
    assert store.advance(*inputs(now, 101), now=now)['status'] == 'GO'
    now += timedelta(seconds=10)
    args = inputs(now, 110)
    args[1]['state'] = 'CONFLICT'
    assert store.advance(*args, now=now)['status'] == 'WARNING'
    now += timedelta(seconds=10)
    assert store.advance(*inputs(now, 110), now=now)['status'] == 'HOLD'


@pytest.mark.parametrize('open_plan', [False, True])
def test_session_end_does_not_invent_exit_fill(tmp_path, open_plan):
    store = ShadowLifecycle(str(tmp_path/'signals.db'))
    store.advance(*inputs(), now=NOW)
    if open_plan:
        at = NOW+timedelta(seconds=10)
        store.advance(*inputs(at, 101), now=at)
    end = NOW.replace(hour=15, minute=20)
    result = store.advance(*inputs(end, ready=False), now=end)
    assert result['status'] == ('EXIT' if open_plan else 'CANCEL')
    assert result['exit_price'] is None
    assert result['authorization'] == 'NONE'


@pytest.mark.parametrize('hour,minute', [(9, 0), (15, 10), (15, 20), (15, 39)])
def test_no_new_plan_outside_entry_window(tmp_path, hour, minute):
    store = ShadowLifecycle(str(tmp_path/'signals.db'))
    now = NOW.replace(hour=hour, minute=minute)
    result = store.advance(*inputs(now), now=now)
    assert result['authorization'] == 'NONE'
    assert store.snapshot()['current'] is None


@pytest.mark.parametrize('price', [float('nan'), -1, 0, float('inf')])
def test_invalid_plan_fails_closed(tmp_path, price):
    store = ShadowLifecycle(str(tmp_path/'signals.db'))
    args = inputs()
    args[0]['reference_entry'] = price
    assert store.advance(*args, now=NOW)['authorization'] == 'NONE'
    assert store.snapshot()['current'] is None


def test_signal_api_reads_persisted_transitions(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from dantex import api
    path = str(tmp_path/'api-signals.db')
    monkeypatch.setattr(api.validation_recorder, 'path', path)
    store = ShadowLifecycle(path)
    store.advance(*inputs(), now=NOW)
    later = NOW + timedelta(seconds=10)
    store.advance(*inputs(later, 101), now=later)
    response = TestClient(api.app).get('/v1/signals')
    assert response.status_code == 200
    payload = response.json()
    assert payload['current']['status'] == 'GO'
    assert [e['status'] for e in payload['events']] == ['GO', 'WAIT']
    assert payload['current']['authorization'] == 'SHADOW_ONLY'
    assert payload['probability'] is None


def test_api_persistence_failure_is_blocked(monkeypatch):
    from dantex import api
    def fail(*args):
        raise OSError('unavailable')
    monkeypatch.setattr(api, 'ShadowLifecycle', fail)
    result = api.paper_lifecycle(*inputs())
    assert result['authorization'] == 'NONE'
    assert result['tracking_status'] == 'UNAVAILABLE'
