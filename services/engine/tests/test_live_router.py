from datetime import datetime, timedelta, timezone

from dantex.live_router import route_tick


def test_fresh_tick_can_enter_engine():
    now = datetime.now(timezone.utc)
    x = route_tick(
        instrument_key="NSE_INDEX|Nifty 50", payload={"ltp": 23400},
        received_at=now, provider_timestamp=now - timedelta(seconds=1),
    )
    assert x.quality.usable


def test_stale_tick_is_blocked_before_decision_engine():
    now = datetime.now(timezone.utc)
    x = route_tick(
        instrument_key="NSE_INDEX|Nifty 50", payload={"ltp": 23400},
        received_at=now, provider_timestamp=now - timedelta(seconds=12),
    )
    assert not x.quality.usable
