from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .domain import Lifecycle, Side
from .state import ArmedPlan, LiveSignalState, evaluate_armed


@dataclass(frozen=True)
class ShadowTick:
    timestamp: datetime
    price: float


@dataclass(frozen=True)
class ShadowResult:
    final_state: LiveSignalState
    path: tuple[Lifecycle, ...]


def replay(plan: ArmedPlan, ticks: list[ShadowTick]) -> ShadowResult:
    if not ticks:
        raise ValueError("shadow replay requires ticks")
    state = LiveSignalState(plan, Lifecycle.ARMED, plan.armed_at, "shadow replay armed")
    path: list[Lifecycle] = [state.lifecycle]
    for tick in ticks:
        state = evaluate_armed(state, price=tick.price, at=tick.timestamp)
        if state.lifecycle != path[-1]:
            path.append(state.lifecycle)
        if state.lifecycle in {Lifecycle.GO, Lifecycle.CANCEL}:
            break
    return ShadowResult(state, tuple(path))
