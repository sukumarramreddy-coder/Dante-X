from __future__ import annotations

from dataclasses import dataclass

from .domain import Side
from .risk import size_position


@dataclass(frozen=True)
class ExecutionPlan:
    side: Side
    trigger: float
    entry_low: float
    entry_high: float
    stop: float
    target1: float
    target2: float
    cancel_level: float
    quantity: int
    net_r_multiple: float


def build_plan(
    *,
    side: Side,
    trigger: float,
    entry_low: float,
    entry_high: float,
    stop: float,
    target1: float,
    target2: float,
    cancel_level: float,
    risk_budget_inr: float,
    lot_size: int,
    estimated_costs_inr: float,
) -> ExecutionPlan:
    entry = (entry_low + entry_high) / 2
    if side == Side.BULLISH and not (stop < entry < target1 <= target2):
        raise ValueError("invalid bullish payoff geometry")
    if side == Side.BEARISH and not (stop > entry > target1 >= target2):
        raise ValueError("invalid bearish payoff geometry")
    risk = size_position(
        risk_budget_inr=risk_budget_inr,
        entry=entry,
        stop=stop,
        target=target1,
        lot_size=lot_size,
        estimated_costs_inr=estimated_costs_inr,
    )
    return ExecutionPlan(
        side=side,
        trigger=trigger,
        entry_low=entry_low,
        entry_high=entry_high,
        stop=stop,
        target1=target1,
        target2=target2,
        cancel_level=cancel_level,
        quantity=risk.quantity,
        net_r_multiple=risk.net_r_multiple,
    )
