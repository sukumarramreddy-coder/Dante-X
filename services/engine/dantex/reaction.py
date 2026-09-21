from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Reaction(StrEnum):
    CONFIRMED = "confirmed"
    ABSORBED = "absorbed"
    REFUSED = "refused"
    OVERSHOT = "overshot"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class ReactionAssessment:
    reaction: Reaction
    bullish_adjustment: float
    bearish_adjustment: float
    reason: str


def assess_reaction(
    *,
    expected_direction: int,
    actual_return: float,
    breadth_change: float,
    volatility_change: float,
    threshold: float = 0.15,
) -> ReactionAssessment:
    if expected_direction not in {-1, 1}:
        raise ValueError("expected_direction must be -1 or 1")
    aligned = actual_return * expected_direction
    if aligned >= threshold:
        boost = min(15.0, 5 + abs(actual_return) * 10)
        if expected_direction > 0:
            return ReactionAssessment(Reaction.CONFIRMED, boost, 0, "market confirms positive catalyst")
        return ReactionAssessment(Reaction.CONFIRMED, 0, boost, "market confirms negative catalyst")
    if aligned <= -threshold:
        boost = min(18.0, 7 + abs(actual_return) * 12)
        if expected_direction < 0 and breadth_change > 0 and volatility_change <= 0:
            return ReactionAssessment(Reaction.REFUSED, boost, -boost / 2, "bad news refused: breadth improves and volatility does not confirm")
        if expected_direction > 0 and breadth_change < 0 and volatility_change >= 0:
            return ReactionAssessment(Reaction.REFUSED, -boost / 2, boost, "good news refused: breadth deteriorates and volatility confirms risk")
        return ReactionAssessment(Reaction.ABSORBED, boost if actual_return > 0 else 0, boost if actual_return < 0 else 0, "expected reaction absorbed")
    return ReactionAssessment(Reaction.INCONCLUSIVE, 0, 0, "response too small to classify")
