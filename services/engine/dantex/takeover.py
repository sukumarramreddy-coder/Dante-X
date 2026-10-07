from __future__ import annotations

from dataclasses import dataclass

from .domain import Side


@dataclass(frozen=True)
class Takeover:
    authorized: bool
    side: Side | None
    reason: str


def authorize_takeover(
    *,
    cancelled_side: Side,
    bullish_score: float,
    bearish_score: float,
    opposite_executable: bool,
    minimum_score: float = 65,
    minimum_margin: float = 15,
) -> Takeover:
    opposite = Side.BEARISH if cancelled_side == Side.BULLISH else Side.BULLISH
    new_score = bearish_score if opposite == Side.BEARISH else bullish_score
    old_score = bullish_score if cancelled_side == Side.BULLISH else bearish_score
    if not opposite_executable:
        return Takeover(False, None, "opposite instrument is not executable")
    if new_score < minimum_score or new_score - old_score < minimum_margin:
        return Takeover(False, None, "opposite thesis has not independently authorized")
    return Takeover(True, opposite, "cancelled thesis replaced by independently authorized opposite")
