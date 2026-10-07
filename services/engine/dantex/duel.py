from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .domain import Side


class DuelStatus(StrEnum):
    NO_EDGE = "no_edge"
    BULLISH_LEAD = "bullish_lead"
    BEARISH_LEAD = "bearish_lead"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class Thesis:
    side: Side
    score: float
    executable: bool
    path_match: float
    potential_left: float


@dataclass(frozen=True)
class DuelDecision:
    status: DuelStatus
    leader: Side | None
    margin: float
    reason: str


def resolve_duel(
    bullish: Thesis,
    bearish: Thesis,
    *,
    minimum_score: float = 60,
    minimum_margin: float = 10,
) -> DuelDecision:
    eligible = [x for x in (bullish, bearish) if x.executable and x.score >= minimum_score]
    if not eligible:
        return DuelDecision(DuelStatus.NO_EDGE, None, 0, "neither side independently authorized")
    if len(eligible) == 1:
        winner = eligible[0]
        status = DuelStatus.BULLISH_LEAD if winner.side == Side.BULLISH else DuelStatus.BEARISH_LEAD
        return DuelDecision(status, winner.side, winner.score, "only one side independently authorized")
    margin = abs(bullish.score - bearish.score)
    if margin < minimum_margin:
        return DuelDecision(DuelStatus.CONFLICT, None, margin, "both sides strong; edge is not asymmetric")
    winner = bullish if bullish.score > bearish.score else bearish
    status = DuelStatus.BULLISH_LEAD if winner.side == Side.BULLISH else DuelStatus.BEARISH_LEAD
    return DuelDecision(status, winner.side, margin, "independent thesis leads by required margin")
