from dantex.circuit_breaker import daily_loss_circuit


def test_open_risk_counts_against_daily_circuit():
    x = daily_loss_circuit(realized_pnl=-700, open_risk=300, max_daily_loss=1000)
    assert not x.trading_allowed


def test_profit_does_not_expand_loss_budget():
    x = daily_loss_circuit(realized_pnl=500, open_risk=200, max_daily_loss=1000)
    assert x.remaining_loss_budget == 800
