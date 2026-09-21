from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .quality import DataQuality


@dataclass(frozen=True)
class RoutedTick:
    instrument_key: str
    received_at: datetime
    payload: dict
    quality: DataQuality


def route_tick(
    *,
    instrument_key: str,
    payload: dict,
    received_at: datetime,
    provider_timestamp: datetime,
    max_age_seconds: float = 5,
) -> RoutedTick:
    age = (received_at - provider_timestamp).total_seconds()
    usable = 0 <= age <= max_age_seconds
    quality = DataQuality(
        usable=usable,
        freshness_seconds=max(0, age),
        completeness=1.0 if payload else 0.0,
        reason="fresh live tick" if usable and payload else "stale or incomplete live tick",
    )
    return RoutedTick(instrument_key, received_at, payload, quality)
