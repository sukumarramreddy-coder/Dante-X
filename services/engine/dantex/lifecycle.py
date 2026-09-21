from __future__ import annotations
from .domain import Lifecycle

_ALLOWED = {
    Lifecycle.NO_EDGE: {Lifecycle.DETECTED},
    Lifecycle.DETECTED: {Lifecycle.WATCH, Lifecycle.ARMED, Lifecycle.CANCEL},
    Lifecycle.WATCH: {Lifecycle.ARMED, Lifecycle.CANCEL, Lifecycle.NO_EDGE},
    Lifecycle.ARMED: {Lifecycle.GO, Lifecycle.CANCEL},
    Lifecycle.GO: {Lifecycle.HOLD, Lifecycle.RUN, Lifecycle.WARNING, Lifecycle.EXIT},
    Lifecycle.HOLD: {Lifecycle.RUN, Lifecycle.WARNING, Lifecycle.EXIT},
    Lifecycle.RUN: {Lifecycle.HOLD, Lifecycle.WARNING, Lifecycle.EXIT},
    Lifecycle.WARNING: {Lifecycle.HOLD, Lifecycle.EXIT},
    Lifecycle.EXIT: set(),
    Lifecycle.CANCEL: set(),
}


def assert_transition(current: Lifecycle, nxt: Lifecycle) -> None:
    if nxt not in _ALLOWED[current]:
        raise ValueError(f"Illegal signal transition: {current} -> {nxt}")
