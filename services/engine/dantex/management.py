from __future__ import annotations

from dataclasses import dataclass

from .domain import Lifecycle, Side


@dataclass(frozen=True)
class ManagementDecision:
    lifecycle: Lifecycle
    reason: str


def manage_open_trade(
    *,
    side: Side,
    current: float,
    stop: float,
    target1: float,
    target2: float,
    path_score: float,
    option_confirming: bool,
) -> ManagementDecision:
    stop_failed = current <= stop if side == Side.BULLISH else current >= stop
    t2_hit = current >= target2 if side == Side.BULLISH else current <= target2
    t1_hit = current >= target1 if side == Side.BULLISH else current <= target1

    if stop_failed:
        return ManagementDecision(Lifecycle.EXIT, "structural stop failed")
    if not option_confirming or path_score < 35:
        return ManagementDecision(Lifecycle.WARNING, "live path or option confirmation deteriorated")
    if t2_hit:
        return ManagementDecision(Lifecycle.RUN, "second target reached with confirmation intact")
    if t1_hit:
        return ManagementDecision(Lifecycle.HOLD, "first target reached; manage continuation")
    return ManagementDecision(Lifecycle.HOLD, "thesis remains intact")
