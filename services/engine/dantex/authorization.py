from __future__ import annotations

from dataclasses import dataclass
from .features import HypothesisScore


@dataclass(frozen=True)
class ExecutionQuality:
    liquidity: float
    spread: float
    potential_left: float
    net_r_multiple: float


@dataclass(frozen=True)
class Authorization:
    allowed: bool
    reason: str


def authorize(
    hypothesis: HypothesisScore,
    quality: ExecutionQuality,
    *,
    min_families: int = 3,
    min_direction_score: float = 55,
    min_liquidity: float = 60,
    min_spread: float = 60,
    min_potential: float = 45,
    min_rr: float = 1.25,
) -> Authorization:
    if hypothesis.independent_families < min_families:
        return Authorization(False, "insufficient independent evidence")
    if max(hypothesis.bullish, hypothesis.bearish) < min_direction_score:
        return Authorization(False, "no directional edge")
    if quality.liquidity < min_liquidity or quality.spread < min_spread:
        return Authorization(False, "instrument execution quality is poor")
    if quality.potential_left < min_potential:
        return Authorization(False, "move is too spent to chase")
    if quality.net_r_multiple < min_rr:
        return Authorization(False, "net reward/risk is insufficient")
    return Authorization(True, "authorized")
