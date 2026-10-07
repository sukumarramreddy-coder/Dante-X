from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .domain import Lifecycle, Side
from .outcomes import Excursion, measure_excursion
from .state import ArmedPlan, LiveSignalState, evaluate_armed


@dataclass(frozen=True)
class SimTick:
    timestamp: datetime
    underlying: float
    premium: float


@dataclass(frozen=True)
class SessionResult:
    lifecycle_path: tuple[Lifecycle, ...]
    trigger_time: datetime | None
    excursion: Excursion | None
    final_underlying: float
    final_premium: float


def simulate_session(
    *,
    plan: ArmedPlan,
    ticks: list[SimTick],
    premium_entry: float,
    premium_stop: float,
    premium_target1: float,
    premium_target2: float,
) -> SessionResult:
    if not ticks:
        raise ValueError("session requires ticks")
    state = LiveSignalState(plan, Lifecycle.ARMED, plan.armed_at, "simulation armed")
    path = [Lifecycle.ARMED]
    trigger_time = None
    post_entry: list[float] = []

    for tick in ticks:
        before = state.lifecycle
        state = evaluate_armed(state, price=tick.underlying, at=tick.timestamp)
        if state.lifecycle != before:
            path.append(state.lifecycle)
        if state.lifecycle == Lifecycle.GO and trigger_time is None:
            trigger_time = tick.timestamp
        if trigger_time is not None and tick.timestamp >= trigger_time:
            post_entry.append(tick.premium)
        if state.lifecycle == Lifecycle.CANCEL:
            break

    excursion = None
    if post_entry:
        excursion = measure_excursion(
            side=Side.BULLISH,
            entry=premium_entry,
            stop=premium_stop,
            target1=premium_target1,
            target2=premium_target2,
            prices=post_entry,
        )
    last = ticks[-1]
    return SessionResult(tuple(path), trigger_time, excursion, last.underlying, last.premium)
