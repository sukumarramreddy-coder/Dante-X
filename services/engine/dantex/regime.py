from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Regime(StrEnum):
    TREND = "trend"
    RANGE = "range"
    VOLATILE = "volatile"
    COMPRESSION = "compression"


@dataclass(frozen=True)
class RegimeState:
    regime: Regime
    confidence: float


def classify_regime(*, atr_pct: float, trend_strength: float, compression: float) -> RegimeState:
    if compression >= 70:
        return RegimeState(Regime.COMPRESSION, min(100, compression))
    if atr_pct >= 1.5:
        return RegimeState(Regime.VOLATILE, min(100, atr_pct * 40))
    if trend_strength >= 65:
        return RegimeState(Regime.TREND, min(100, trend_strength))
    return RegimeState(Regime.RANGE, min(100, 100 - trend_strength / 2))
