from __future__ import annotations

from math import floor
from .domain import RiskPlan


def size_position(
    *,
    risk_budget_inr: float,
    entry: float,
    stop: float,
    target: float,
    lot_size: int = 1,
    estimated_costs_inr: float = 0.0,
) -> RiskPlan:
    """Size only after the natural stop is known."""
    if lot_size <= 0:
        raise ValueError("lot_size must be positive")
    per_unit = abs(entry - stop)
    if per_unit <= 0:
        raise ValueError("entry and stop must differ")
    usable = risk_budget_inr - estimated_costs_inr
    if usable <= 0:
        raise ValueError("costs consume the risk budget")
    lots = floor(usable / (per_unit * lot_size))
    if lots < 1:
        raise ValueError("risk budget cannot support one lot at this stop")
    qty = lots * lot_size
    gross_reward = abs(target - entry) * qty
    expected_reward = max(0.0, gross_reward - estimated_costs_inr)
    actual_risk = per_unit * qty + estimated_costs_inr
    return RiskPlan(
        risk_budget_inr=risk_budget_inr,
        risk_per_unit_inr=per_unit,
        quantity=qty,
        estimated_costs_inr=estimated_costs_inr,
        expected_reward_inr=expected_reward,
        net_r_multiple=round(expected_reward / actual_risk, 3),
    )
