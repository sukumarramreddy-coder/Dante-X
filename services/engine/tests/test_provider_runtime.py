from datetime import datetime, timedelta, timezone

from dantex.providers.provider_state import ProviderState
from dantex.providers.runtime import ProviderRuntime


def test_provider_cannot_authorize_until_fresh_snapshot():
    now = datetime.now(timezone.utc)
    r = ProviderRuntime.offline()
    r.begin_connect(now)
    r.authorized(now)
    r.observe("market_info", now)
    assert not r.authorization_allowed
    r.observe("live_feed", now)
    assert r.authorization_allowed
    assert r.status.state == ProviderState.LIVE


def test_live_provider_turns_stale_and_blocks_authorization():
    now = datetime.now(timezone.utc)
    r = ProviderRuntime.offline()
    r.begin_connect(now)
    r.authorized(now)
    r.observe("market_info", now)
    r.observe("live_feed", now)
    r.freshness_check(now + timedelta(seconds=10), max_age_seconds=5)
    assert r.status.state == ProviderState.STALE
    assert not r.authorization_allowed
