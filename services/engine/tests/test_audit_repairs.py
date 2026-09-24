from datetime import datetime, timedelta

import pytest

from dantex.freshness import IST, gate, market_session
from dantex.observation_loop import ObservationLoop, _market_window
from dantex.providers.options_intelligence import OptionsIntelligence


@pytest.mark.parametrize('seconds', [1, 60, 86400])
def test_future_source_timestamp_is_ineligible(seconds):
    now = datetime(2026, 9, 24, 12, tzinfo=IST)
    result = gate(source='BREADTH', timestamp=(now + timedelta(seconds=seconds)).isoformat(), now=now)
    assert not result['eligible']
    assert 'source timestamp is in the future' in result['reasons']


def rows(strike, call=100, put=100, suffix=''):
    return [{'strike': strike,
             'call': {'ltp': call, 'instrument_key': f'{strike}CE{suffix}'},
             'put': {'ltp': put, 'instrument_key': f'{strike}PE{suffix}'}}]


@pytest.mark.parametrize('change', ['strike', 'instrument', 'expiry', 'session'])
def test_option_baseline_resets_on_identity_change(change):
    tracker = OptionsIntelligence()
    tracker._track('NIFTY', 23000, 23000, rows(23000), expiry='2026-09-29')
    strike = 23050 if change == 'strike' else 23000
    suffix = 'new' if change == 'instrument' else ''
    expiry = '2026-10-06' if change == 'expiry' else '2026-09-29'
    if change == 'session':
        tracker._history['NIFTY'][-1]['session_date'] = '2000-01-01'
    result = tracker._track('NIFTY', 23040, strike, rows(strike, 90, 110, suffix), expiry=expiry)
    assert result == {'state': 'BUILDING_BASELINE', 'samples': 1}
    result = tracker._track('NIFTY', 23050, strike, rows(strike, 99, 99, suffix), expiry=expiry)
    assert result['state'] == 'CE_STRENGTHENING'
    assert result['atm_call_change_pct'] == 10
    assert result['atm_put_change_pct'] == -10


@pytest.mark.parametrize('hour,minute,second,expected', [
    (9, 14, 59, False), (9, 15, 0, True), (15, 29, 59, True),
    (15, 30, 1, True), (15, 39, 0, True), (15, 39, 59, True), (15, 40, 0, False),
])
def test_recording_window_boundaries(hour, minute, second, expected):
    now = datetime(2026, 9, 24, hour, minute, second, tzinfo=IST)
    assert _market_window(now) is expected
    if hour == 15 and minute >= 30 and (minute > 30 or second > 0):
        assert not market_session(now)['market_open']


def test_recording_window_weekend_and_timezone():
    from datetime import timezone
    assert not _market_window(datetime(2026, 9, 26, 15, 39, tzinfo=IST))
    now = datetime(2026, 9, 24, 15, 39, tzinfo=IST)
    assert _market_window(now.astimezone(timezone.utc))


def test_post_market_record_is_persisted_without_live_eligibility(monkeypatch):
    from dantex import observation_loop as module

    fixed = datetime(2026, 9, 24, 15, 39, 30, tzinfo=IST)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)

    class StopLoop(BaseException):
        pass

    def stop(_):
        raise StopLoop()

    records = []
    monkeypatch.setattr(module, 'datetime', Clock)
    monkeypatch.setattr(module, 'sleep', stop)
    monkeypatch.setattr(module.instrument_master, 'refresh_async', lambda: None)
    monkeypatch.setattr(module.options_intelligence, 'snapshot', lambda symbol: {'status': 'OK', 'spot': 23000})
    monkeypatch.setattr(module.validation_recorder, 'record_duel', lambda *args: records.append(args))
    monkeypatch.setattr(module.validation_recorder, 'status', lambda: {'external_configured': False})
    loop = ObservationLoop()
    outcomes = []
    monkeypatch.setattr(loop._outcomes, 'observe', lambda snapshots: outcomes.append(snapshots))
    with pytest.raises(StopLoop):
        loop._run()
    assert len(records) == 1
    assert records[0][0]['readiness']['post_market_context']
    assert records[0][1]['authorization'] == 'NONE'
    assert not outcomes
    status = loop.snapshot()
    assert status['samples'] == 1
    assert status['state'] == 'POST_MARKET_SAMPLING'
    assert status['freshness'] == 'STALE_CONTEXT'
    assert not status['live_authorization_eligible']
