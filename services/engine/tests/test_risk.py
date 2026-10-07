import pytest
from dantex.risk import size_position


def test_position_size_respects_lot_and_budget():
    p = size_position(
        risk_budget_inr=1000,
        entry=100,
        stop=90,
        target=120,
        lot_size=65,
        estimated_costs_inr=50,
    )
    assert p.quantity == 65
    assert p.risk_per_unit_inr == 10
    assert p.net_r_multiple > 1


def test_rejects_impossible_stop():
    with pytest.raises(ValueError):
        size_position(risk_budget_inr=1000, entry=100, stop=100, target=120)
