from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from dantex.freshness import IST, gate
from dantex.validation_recorder import ValidationRecorder


@pytest.fixture
def recorder(tmp_path, monkeypatch):
    for key in ('DANTEX_VALIDATION_REST_URL', 'DANTEX_VALIDATION_REST_KEY', 'DANTEX_VALIDATION_DURABLE'):
        monkeypatch.delenv(key, raising=False)
    return ValidationRecorder(str(tmp_path / 'validation.sqlite3'))


def test_local_path_does_not_prove_durability(recorder):
    recorder.record_duel({'state': 'DIAGNOSTIC'})
    state = recorder.status()
    assert not state['persistent']
    assert not state['durable_ready']
    assert not state['calibration_ready']


def test_configured_external_sink_must_succeed_and_remain_healthy(recorder, monkeypatch):
    monkeypatch.setenv('DANTEX_VALIDATION_REST_URL', 'https://example.invalid/rows')
    monkeypatch.setenv('DANTEX_VALIDATION_REST_KEY', 'secret-test-token')
    assert not recorder.status()['durable_ready']
    monkeypatch.setattr(recorder, '_external_write', lambda row: True)
    recorder.record_duel({'state': 'DIAGNOSTIC'})
    assert recorder.status()['durable_ready']
    recorder.last_external_write_at -= timedelta(seconds=61)
    assert not recorder.status()['durable_ready']
    def fail(row):
        raise OSError('secret-test-token https://private.invalid/?token=secret')
    monkeypatch.setattr(recorder, '_external_write', fail)
    recorder.record_duel({'state': 'DIAGNOSTIC'})
    state = recorder.status()
    assert state['samples'] == 2
    assert state['external_write']['failures'] == 1
    assert state['external_write']['last_error'] == 'OSError'
    assert not state['durable_ready']
    assert 'secret-test-token' not in str(state)


def test_partial_or_insecure_sink_fails_without_losing_local_record(recorder, monkeypatch):
    monkeypatch.setenv('DANTEX_VALIDATION_REST_URL', 'http://example.invalid/rows')
    recorder.record_duel({'state': 'DIAGNOSTIC'})
    assert recorder.status()['external_write']['failures'] == 1
    monkeypatch.setenv('DANTEX_VALIDATION_REST_KEY', 'secret')
    recorder.record_duel({'state': 'DIAGNOSTIC'})
    assert recorder.status()['samples'] == 2
    assert not recorder.status()['durable_ready']


def test_external_failure_cannot_fall_back_to_local_freshness(monkeypatch):
    from dantex import observation_loop as module
    loop = module.ObservationLoop()
    loop.last_persisted_at = datetime.now(timezone.utc)
    monkeypatch.setattr(module.validation_recorder, 'status', lambda: {
        'external_configured': True, 'durable_ready': False,
        'external_write': {'last_success_at': None, 'last_error': 'OSError'}})
    result = loop.snapshot()
    assert result['freshness'] == 'UNKNOWN'
    assert result['last_persisted_at'] is None
    assert not result['live_authorization_eligible']
    assert not result['live_observation_eligible']


@pytest.mark.parametrize('timestamp', [None, '', 123, {}, 'bad', '2026-09-24T12:00:00'])
def test_missing_or_ambiguous_timestamp_is_blocked(timestamp):
    result = gate(source='test', timestamp=timestamp, provider_fresh=True,
                  now=datetime(2026, 9, 24, 12, tzinfo=IST))
    assert not result['eligible']


def test_lifespan_starts_observers_without_deprecated_hooks(monkeypatch):
    from dantex import api
    started = []
    monkeypatch.setattr(api, 'start_shadow_observers', lambda: started.append(True))
    monkeypatch.setattr(api.observation_loop, 'snapshot', lambda: {'freshness': 'LIVE', 'live_observation_eligible': False})
    monkeypatch.setattr(api.validation_recorder, 'status', dict)
    with TestClient(api.app) as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert not response.json()['live_data']['eligible']
    assert started == [True]
    assert not api.app.router.on_startup


def test_unproven_option_snapshots_cannot_label_outcomes():
    from dantex.outcome_tracker import OutcomeTracker
    recorded = (datetime.now(IST) - timedelta(hours=1)).isoformat()
    sample = {'id': 1, 'recorded_at': recorded, 'decision': {
        'status': 'DETECTED', 'contract': {'instrument_key': 'option'},
        'entry': 100, 'stop': 90, 't1': 110, 't2': 120}}
    labels = []
    tracker = OutcomeTracker(SimpleNamespace(unlabelled=lambda limit, **kwargs: [sample], label=lambda *args: labels.append(args)))
    tracker.observe({'NIFTY': {'strikes': [{'call': {'instrument_key': 'option', 'ltp': 120}}]}})
    assert not labels
    assert not tracker.paths


@pytest.mark.parametrize('price,timestamp_offset', [(float('nan'), 0), (float('inf'), 0), (True, 0), (-1, 0), (100, 1), (100, -16)])
def test_invalid_provider_tick_cannot_refresh_heartbeat(price, timestamp_offset):
    from dantex.providers.tick_integrity import valid_tick
    now = datetime.now(timezone.utc)
    assert valid_tick({'ltp': price, 'ltt': int((now.timestamp() + timestamp_offset) * 1000)}, now) is None


def test_credentials_do_not_leak_through_repr():
    from dantex.providers.credentials import UpstoxCredentials
    from dantex.providers.upstox import UpstoxConfig
    assert 'test-secret' not in repr(UpstoxCredentials('test-secret'))
    assert 'test-secret' not in repr(UpstoxConfig('test-secret'))


def test_historical_or_unordered_rows_cannot_label_forward_outcome():
    from dantex.outcome_labeler import label_from_path
    now = datetime.now(IST)
    start = now - timedelta(minutes=5)
    sample = {'recorded_at': start.isoformat(), 'decision': {
        'status': 'DETECTED', 'entry': 100, 'stop': 90, 't1': 110, 't2': 120}}
    earlier = {'at': (start - timedelta(seconds=1)).isoformat(), 'premium': 120}
    later = {'at': (start + timedelta(seconds=30)).isoformat(), 'premium': 110}
    assert label_from_path(sample, [earlier]) is None
    assert label_from_path(sample, [later, earlier]) is None
    assert label_from_path(sample, [later])['first_event'] == 'T1'


def test_sink_redirect_never_forwards_credentials():
    from dantex.validation_recorder import NoCredentialRedirect
    with pytest.raises(RuntimeError, match='redirect refused'):
        NoCredentialRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid')


def test_temporary_storage_cannot_be_attested_as_durable(tmp_path, monkeypatch):
    import tempfile
    monkeypatch.setenv('DANTEX_VALIDATION_DURABLE', 'true')
    monkeypatch.delenv('DANTEX_VALIDATION_REST_URL', raising=False)
    monkeypatch.delenv('DANTEX_VALIDATION_REST_KEY', raising=False)
    monkeypatch.setattr(tempfile, 'gettempdir', lambda: str(tmp_path))
    recorder = ValidationRecorder(str(tmp_path / 'temporary.sqlite3'))
    assert not recorder.status()['durable_ready']


def test_nifty_probe_ignores_other_instruments_and_malformed_ticks(monkeypatch):
    import sys
    from dantex.providers.upstox_live import NiftyLiveProbe
    callbacks = {}
    class Stream:
        def __init__(self, *args):pass
        def on(self, event, callback):callbacks[event] = callback
        def auto_reconnect(self, *args):pass
        def connect(self):pass
    monkeypatch.setenv('UPSTOX_ANALYTICS_TOKEN', 'test-secret')
    monkeypatch.setitem(sys.modules, 'upstox_client', SimpleNamespace(
        Configuration=SimpleNamespace, ApiClient=lambda config: config, MarketDataStreamerV3=Stream))
    probe = NiftyLiveProbe()
    probe._run()
    callbacks['open']()
    timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
    callbacks['message']({'feeds': {'WRONG': {'ltpc': {'ltp': 100, 'ltt': timestamp}}}})
    assert probe.received_at is None
    assert probe.snapshot()['state'] != 'LIVE'
    callbacks['message']({'feeds': {probe.instrument_key: {'ltpc': {'ltp': 100, 'ltt': timestamp}}}})
    assert probe.snapshot()['state'] == 'LIVE'
    received = probe.received_at
    callbacks['message']({'feeds': {probe.instrument_key: {'ltpc': {'ltp': 'NaN', 'ltt': timestamp}}}})
    assert probe.received_at == received
    assert probe.snapshot()['state'] != 'LIVE'
