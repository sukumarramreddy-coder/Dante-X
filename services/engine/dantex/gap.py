from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GapDecision:
    executable: bool
    distance_from_trigger: float
    reason: str


def validate_gap(*, trigger: float, observed: float, max_distance: float) -> GapDecision:
    distance = abs(observed - trigger)
    if distance > max_distance:
        return GapDecision(False, distance, "gap exceeds pre-authorized execution distance")
    return GapDecision(True, distance, "within execution tolerance")
