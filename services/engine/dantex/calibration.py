from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalibrationSample:
    score: float
    target_before_stop: bool


@dataclass(frozen=True)
class CalibrationBand:
    lower: float
    upper: float
    samples: int
    observed_rate: float | None
    publishable: bool


def calibration_bands(
    samples: list[CalibrationSample],
    *,
    width: int = 10,
    minimum_samples: int = 100,
) -> list[CalibrationBand]:
    bands: list[CalibrationBand] = []
    for lower in range(0, 100, width):
        upper = lower + width
        bucket = [s for s in samples if lower <= s.score < upper or (upper == 100 and s.score == 100)]
        rate = None if not bucket else sum(s.target_before_stop for s in bucket) / len(bucket) * 100
        bands.append(CalibrationBand(
            lower, upper, len(bucket), None if rate is None else round(rate, 1),
            len(bucket) >= minimum_samples,
        ))
    return bands
