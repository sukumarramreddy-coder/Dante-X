from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Exposure:
    symbol: str
    family: str
    direction: int
    max_loss: float


@dataclass(frozen=True)
class ExposureCheck:
    allowed: bool
    correlated_risk: float
    reason: str


def check_correlated_exposure(
    *,
    existing: list[Exposure],
    new_family: str,
    new_direction: int,
    new_max_loss: float,
    max_correlated_risk: float,
) -> ExposureCheck:
    correlated = sum(
        x.max_loss for x in existing
        if x.family == new_family and x.direction == new_direction
    ) + new_max_loss
    if correlated > max_correlated_risk:
        return ExposureCheck(False, correlated, "correlated exposure limit exceeded")
    return ExposureCheck(True, correlated, "within correlated exposure limit")
