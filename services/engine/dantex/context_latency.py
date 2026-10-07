from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextWeight:
    usable_for_trigger: bool
    maximum_weight: float
    reason: str


def latency_weight(latency_seconds: int) -> ContextWeight:
    if latency_seconds <= 5:
        return ContextWeight(True, 1.0, "near-real-time context")
    if latency_seconds <= 30:
        return ContextWeight(False, 0.5, "delayed context: confirmation only")
    if latency_seconds <= 120:
        return ContextWeight(False, 0.25, "slow context: regime only")
    return ContextWeight(False, 0.1, "heavily delayed context")
