from datetime import UTC, datetime

from dantex.audit import SignalEvent
from dantex.domain import AssetClass, Confidence, Horizon, Lifecycle, PricePlan, RiskPlan, Side, Signal
from dantex.store import SignalStore


def test_signal_audit_round_trip(tmp_path):
    signal = Signal(
        signal_id="abc", created_at=datetime.now(UTC), symbol="NIFTY",
        asset_class=AssetClass.INDEX_OPTION, side=Side.BULLISH, horizon=Horizon.INTRADAY,
        lifecycle=Lifecycle.ARMED, contract="TEST",
        plan=PricePlan(underlying_trigger=101, entry_low=10, entry_high=11, stop=8, targets=[14, 17]),
        risk=RiskPlan(risk_budget_inr=1000, risk_per_unit_inr=3, quantity=65,
                      estimated_costs_inr=50, expected_reward_inr=500, net_r_multiple=2),
        confidence=Confidence(live_confirmation=70, path_match=60, potential_left=80),
        evidence=["price", "breadth", "options"], invalidation_reason="structure failed",
    )
    store = SignalStore(tmp_path / "test.db")
    store.save_signal(signal)
    store.append_event(SignalEvent(timestamp=datetime.now(UTC), signal_id="abc",
                                   previous=None, current=Lifecycle.ARMED, reason="authorized"))
    loaded = store.get("abc")
    assert loaded is not None
    assert loaded.signal.plan.underlying_trigger == 101
    assert len(loaded.events) == 1
