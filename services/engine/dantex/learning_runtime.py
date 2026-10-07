"""Read-only orchestration for the persisted learning window."""
from datetime import datetime, timedelta
from functools import lru_cache

from .learning import IST, learning_from_env, timestamp


@lru_cache(maxsize=1)
def learning_window():
    return learning_from_env()


def collect_learning(decision, client, *, now=None, window=None):
    now = timestamp(now or datetime.now(IST))
    window = window or learning_window()
    window.record_collection(decision, now)
    # Finish old events before admitting the next; never read labels to choose
    # the already-frozen probability for a validation event.
    for event in window.pending(now):
        at = timestamp(event["as_of"])
        if at.date() != now.date():
            window.resolve(event["id"], [], now=now)  # no silent historical backfill
            continue
        raw = client.intraday_candles(event["contract"], unit="minutes", interval=1)
        bars = []
        try:
            for row in (raw.get("data") or {}).get("candles") or []:
                stamp = timestamp(row[0])
                if at <= stamp < at + timedelta(minutes=30):
                    bars.append({"at": stamp, "contract": event["contract"], "low": row[3], "high": row[2]})
            bars.sort(key=lambda b: b["at"])
        except (TypeError, ValueError, IndexError):
            bars = []
        # Allow five minutes for provider publication before censoring absence.
        if not bars and now < at + timedelta(minutes=35):
            continue
        window.resolve(event["id"], bars, now=now)
    window.admit(decision, now=now)
    return window.report(now)
