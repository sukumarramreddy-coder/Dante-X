from __future__ import annotations

from dataclasses import dataclass

from .domain import Lifecycle, Side


@dataclass(frozen=True)
class SideState:
    side: Side
    lifecycle: Lifecycle
    score: float
    trigger: float | None
    cancel_level: float | None


@dataclass(frozen=True)
class SignalBook:
    bullish: SideState
    bearish: SideState

    def active(self) -> SideState | None:
        active = [x for x in (self.bullish, self.bearish) if x.lifecycle in {Lifecycle.ARMED, Lifecycle.GO}]
        if len(active) != 1:
            return None
        return active[0]
