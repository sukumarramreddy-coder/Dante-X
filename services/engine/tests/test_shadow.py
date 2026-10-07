from datetime import UTC, datetime, timedelta

from dantex.domain import Lifecycle, Side
from dantex.shadow import ShadowTick, replay
from dantex.state import ArmedPlan


def test_shadow_replay_preserves_trigger_until_go():
    now = datetime.now(UTC)
    plan = ArmedPlan("x", Side.BULLISH, 101, 97, now, now + timedelta(hours=1))
    result = replay(plan, [
        ShadowTick(now + timedelta(minutes=1), 100.8),
        ShadowTick(now + timedelta(minutes=2), 100.99),
        ShadowTick(now + timedelta(minutes=3), 101),
    ])
    assert result.path == (Lifecycle.ARMED, Lifecycle.GO)
    assert result.final_state.plan.trigger == 101
