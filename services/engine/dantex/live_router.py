from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .quality import DataQuality, assess_data_quality


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
    quality = assess_data_quality(
        now=received_at,
        exchange_timestamp=provider_timestamp,
        max_age_seconds=max_age_seconds,
        required_fields_present=bool(payload),
    )
    return RoutedTick(instrument_key, received_at, payload, quality)
