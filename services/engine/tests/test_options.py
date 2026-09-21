from datetime import UTC, datetime

from dantex.options import OptionState, analyze_option_response, choose_contract


def option(contract, spread=0.2, volume=20000, oi=50000):
    return OptionState(
        contract=contract,
        timestamp=datetime.now(UTC),
        premium=100,
        bid=100 - spread / 2,
        ask=100 + spread / 2,
        delta=0.5,
        gamma=0.01,
        theta=-10,
        vega=5,
        iv=14,
        open_interest=oi,
        oi_change=1000,
        volume=volume,
    )


def test_rejects_illiquid_contract():
    liquid = option("LIQUID")
    dead = option("DEAD", spread=10, volume=0, oi=0)
    assert choose_contract([dead, liquid]).contract == "LIQUID"


def test_option_response_exposes_decay_and_elasticity():
    r = analyze_option_response(
        option("X"),
        premium_change_pct=5,
        underlying_change_pct=0.5,
        minutes_to_close=60,
    )
    assert r.elasticity == 10
    assert r.decay_pressure > 0
