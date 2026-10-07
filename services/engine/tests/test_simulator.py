from datetime import UTC, datetime, timedelta

from dantex.domain import Lifecycle, Side
from dantex.simulator import SimTick, simulate_session
from dantex.state import ArmedPlan


def test_artificial_session_fires_and_measures_move():
    now = datetime.now(UTC)
    plan = ArmedPlan("sim", Side.BULLISH, 101, 97, now, now + timedelta(hours=1))
    ticks = [
        SimTick(now + timedelta(minutes=1), 100, 10),
        SimTick(now + timedelta(minutes=2), 100.9, 10.5),
        SimTick(now + timedelta(minutes=3), 101, 11),
        SimTick(now + timedelta(minutes=4), 103, 14),
        SimTick(now + timedelta(minutes=5), 105, 17),
    ]
    result = simulate_session(
        plan=plan, ticks=ticks, premium_entry=11, premium_stop=8,
        premium_target1=14, premium_target2=17,
    )
    assert result.lifecycle_path == (Lifecycle.ARMED, Lifecycle.GO)
    assert result.excursion is not None
    assert result.excursion.target1_hit
    assert result.excursion.target2_hit
