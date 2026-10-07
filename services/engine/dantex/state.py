from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from .domain import Lifecycle, Side
from .lifecycle import assert_transition


@dataclass(frozen=True)
class ArmedPlan:
    signal_id: str
    side: Side
    trigger: float
    cancel_level: float
    armed_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class LiveSignalState:
    plan: ArmedPlan
    lifecycle: Lifecycle
    last_update: datetime
    reason: str


def transition(state: LiveSignalState, nxt: Lifecycle, *, at: datetime, reason: str) -> LiveSignalState:
    assert_transition(state.lifecycle, nxt)
    return replace(state, lifecycle=nxt, last_update=at, reason=reason)


def evaluate_armed(state: LiveSignalState, *, price: float, at: datetime) -> LiveSignalState:
    if state.lifecycle != Lifecycle.ARMED:
        return state
    if at >= state.plan.expires_at:
        return transition(state, Lifecycle.CANCEL, at=at, reason="signal expired unused")
    if state.plan.side == Side.BULLISH:
        if price <= state.plan.cancel_level:
            return transition(state, Lifecycle.CANCEL, at=at, reason="structural cancellation level failed")
        if price >= state.plan.trigger:
            return transition(state, Lifecycle.GO, at=at, reason="pre-armed bullish trigger fired")
    else:
        if price >= state.plan.cancel_level:
            return transition(state, Lifecycle.CANCEL, at=at, reason="structural cancellation level failed")
        if price <= state.plan.trigger:
            return transition(state, Lifecycle.GO, at=at, reason="pre-armed bearish trigger fired")
    return state
