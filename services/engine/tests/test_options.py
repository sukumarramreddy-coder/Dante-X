from datetime import UTC, datetime

from dantex.options import (
    OptionState,
    analyze_option_response,
    choose_contract,
    rank_contracts,
    strike_intelligence,
)


def option(contract, spread=0.2, volume=20000, oi=50000, delta=0.5, theta=-10, oi_change=1000):
    return OptionState(
        contract=contract,
        timestamp=datetime.now(UTC),
        premium=100,
        bid=100 - spread / 2,
        ask=100 + spread / 2,
        delta=delta,
        gamma=0.01,
        theta=theta,
        vega=5,
        iv=14,
        open_interest=oi,
        oi_change=oi_change,
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


def test_strike_intelligence_keeps_contract_quality_separate_from_direction():
    result = strike_intelligence(option("ATM"), minutes_to_close=180)
    assert result.contract == "ATM"
    assert 0 <= result.strike_score <= 100
    assert result.execution_score > 0
    assert result.decay_penalty > 0


def test_rank_contracts_prefers_better_execution_and_greeks():
    strong = option("STRONG", spread=0.1, volume=20000, oi=50000, delta=0.5)
    weak = option("WEAK", spread=2.0, volume=1000, oi=5000, delta=0.1)
    ranked = rank_contracts([weak, strong], minutes_to_close=180)
    assert [x.contract for x in ranked] == ["STRONG", "WEAK"]


def test_rank_contracts_rejects_non_executable_contracts():
    dead = option("DEAD", spread=10, volume=0, oi=0)
    assert rank_contracts([dead], minutes_to_close=180) == []
