from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LockedTrigger:
    signal_id: str
    trigger: float
    revision: int = 1


def revise_trigger(
    locked: LockedTrigger,
    *,
    new_trigger: float,
    cancelled: bool,
    fresh_evidence: bool,
) -> LockedTrigger:
    if not cancelled:
        raise ValueError("armed trigger cannot be revised before explicit cancellation")
    if not fresh_evidence:
        raise ValueError("new setup requires fresh evidence")
    return LockedTrigger(locked.signal_id, new_trigger, locked.revision + 1)
