from __future__ import annotations

from dataclasses import dataclass

from .domain import Side
from .features import HypothesisScore


@dataclass(frozen=True)
class FlipDecision:
    flip: bool
    new_side: Side | None
    reason: str


def evaluate_flip(
    current_side: Side,
    hypothesis: HypothesisScore,
    *,
    min_new_score: float = 65,
    min_margin: float = 15,
) -> FlipDecision:
    new_side = Side.BEARISH if current_side == Side.BULLISH else Side.BULLISH
    new_score = hypothesis.bearish if new_side == Side.BEARISH else hypothesis.bullish
    old_score = hypothesis.bullish if current_side == Side.BULLISH else hypothesis.bearish
    if new_score >= min_new_score and new_score - old_score >= min_margin:
        return FlipDecision(True, new_side, "opposite hypothesis has independently taken control")
    return FlipDecision(False, None, "no authorized opposite-side takeover")
