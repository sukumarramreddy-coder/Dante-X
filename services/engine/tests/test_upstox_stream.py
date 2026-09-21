from datetime import datetime, timedelta, timezone
import json

from dantex.providers.reconnect import ReconnectPolicy
from dantex.providers.upstox_stream import FeedHealth, FeedMode, Subscription


def test_subscription_matches_v3_binary_request_shape():
    raw = Subscription(("NSE_INDEX|Nifty 50",), FeedMode.FULL).request("abc")
    x = json.loads(raw)
    assert x["method"] == "sub"
    assert x["data"]["mode"] == "full"
    assert x["data"]["instrumentKeys"] == ["NSE_INDEX|Nifty 50"]


def test_feed_requires_status_and_snapshot_before_synchronized():
    h = FeedHealth()
    now = datetime.now(timezone.utc)
    h.observe("market_info", now)
    assert not h.synchronized
    h.observe("live_feed", now)
    assert h.synchronized
    assert not h.stale(now + timedelta(seconds=2))


def test_stale_feed_fails_health():
    h = FeedHealth(last_message_at=datetime.now(timezone.utc) - timedelta(seconds=10))
    assert h.stale(datetime.now(timezone.utc), max_age_seconds=5)


def test_reconnect_backoff_is_bounded():
    p = ReconnectPolicy()
    assert p.delay(0) == 1
    assert p.delay(20) == 30
