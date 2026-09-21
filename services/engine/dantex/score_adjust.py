from __future__ import annotations

from dataclasses import dataclass

from .reaction import ReactionAssessment


@dataclass(frozen=True)
class AdjustedScores:
    bullish: float
    bearish: float


def apply_reaction(*, bullish: float, bearish: float, reaction: ReactionAssessment) -> AdjustedScores:
    return AdjustedScores(
        max(0, min(100, bullish + reaction.bullish_adjustment)),
        max(0, min(100, bearish + reaction.bearish_adjustment)),
    )
