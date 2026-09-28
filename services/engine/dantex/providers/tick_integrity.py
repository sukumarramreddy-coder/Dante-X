"""Shared validation of identified provider ticks, never receipt-only freshness."""
from datetime import datetime
from math import isfinite
from typing import Any


def valid_tick(ltpc: dict[str, Any] | None, now: datetime) -> tuple[float, int] | None:
    if not ltpc or isinstance(ltpc.get('ltp'), bool) or isinstance(ltpc.get('ltt'), bool):
        return None
    try:
        price, timestamp = float(ltpc['ltp']), int(ltpc['ltt'])
        age = now.timestamp() * 1000 - timestamp
        if not isfinite(price) or price <= 0 or not 0 <= age <= 15_000:
            return None
        return price, timestamp
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def tick_fresh(price: float | None, timestamp: int | None, received: datetime | None, now: datetime) -> bool:
    return (received is not None and 0 <= (now - received).total_seconds() <= 15
            and valid_tick({'ltp': price, 'ltt': timestamp}, now) is not None)
