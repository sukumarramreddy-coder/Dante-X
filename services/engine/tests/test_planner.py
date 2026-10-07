import pytest

from dantex.domain import Side
from dantex.planner import build_plan


def test_plan_sizes_after_stop_is_defined():
    p = build_plan(
        side=Side.BULLISH, trigger=101, entry_low=101, entry_high=102,
        stop=98, target1=108, target2=112, cancel_level=97,
        risk_budget_inr=1000, lot_size=65, estimated_costs_inr=50,
    )
    assert p.quantity == 260
    assert p.net_r_multiple > 1


def test_rejects_bad_payoff_geometry():
    with pytest.raises(ValueError):
        build_plan(
            side=Side.BULLISH, trigger=101, entry_low=101, entry_high=102,
            stop=105, target1=108, target2=112, cancel_level=97,
            risk_budget_inr=1000, lot_size=65, estimated_costs_inr=50,
        )
