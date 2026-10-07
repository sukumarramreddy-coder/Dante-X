from datetime import UTC, datetime, timedelta

from dantex.domain import Lifecycle, Side
from dantex.state import ArmedPlan, LiveSignalState, evaluate_armed


def make_state():
    now = datetime.now(UTC)
    return LiveSignalState(
        plan=ArmedPlan("s1", Side.BULLISH, 101, 97, now, now + timedelta(hours=1)),
        lifecycle=Lifecycle.ARMED,
        last_update=now,
        reason="armed",
    )


def test_approaching_trigger_does_not_move_or_fire_it():
    state = make_state()
    result = evaluate_armed(state, price=100.99, at=state.last_update + timedelta(minutes=1))
    assert result.lifecycle == Lifecycle.ARMED
    assert result.plan.trigger == 101


def test_trigger_fires_exactly():
    state = make_state()
    result = evaluate_armed(state, price=101, at=state.last_update + timedelta(minutes=1))
    assert result.lifecycle == Lifecycle.GO


def test_unused_signal_expires():
    state = make_state()
    result = evaluate_armed(state, price=100, at=state.plan.expires_at)
    assert result.lifecycle == Lifecycle.CANCEL
