from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DataQuality:
    usable: bool
    age_seconds: float
    score: float
    reason: str


def assess_data_quality(
    *,
    now: datetime,
    exchange_timestamp: datetime,
    max_age_seconds: float,
    required_fields_present: bool = True,
) -> DataQuality:
    age = max(0.0, (now - exchange_timestamp).total_seconds())
    if not required_fields_present:
        return DataQuality(False, age, 0.0, "required market fields missing")
    if age > max_age_seconds:
        return DataQuality(False, age, 0.0, "market data is stale")
    score = max(0.0, 100.0 * (1 - age / max_age_seconds))
    return DataQuality(True, round(age, 3), round(score, 1), "usable")
