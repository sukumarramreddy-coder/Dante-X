from dantex.costs import conservative_cost_estimate


def test_cost_estimate_includes_slippage():
    c = conservative_cost_estimate(
        quantity=65, entry=100, exit=110, brokerage=40, fee_rate=0.001, slippage_bps=5,
    )
    assert c.total > 40
    assert c.slippage > 0
