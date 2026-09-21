from datetime import UTC, datetime, timedelta

from dantex.quality import assess_data_quality


def test_stale_data_fails_closed():
    now = datetime.now(UTC)
    q = assess_data_quality(now=now, exchange_timestamp=now - timedelta(seconds=20), max_age_seconds=5)
    assert not q.usable
    assert q.score == 0


def test_fresh_data_is_usable():
    now = datetime.now(UTC)
    assert assess_data_quality(now=now, exchange_timestamp=now, max_age_seconds=5).usable
