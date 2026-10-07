from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .divergence import DivergenceState


class Threat(StrEnum):
    NONE = "none"
    FAKE_BREAKOUT = "fake_breakout"
    IMMEDIATE_FAILURE = "immediate_failure"
    OPTION_DIVERGENCE = "option_divergence"
    GAP_THROUGH = "gap_through"
    LATE_CHASE = "late_chase"


@dataclass(frozen=True)
class ThreatAssessment:
    threat: Threat
    block_entry: bool
    reason: str


def assess_threat(
    *,
    trigger: float,
    current: float,
    invalidation: float,
    prior_extreme: float,
    potential_score: float,
    divergence: DivergenceState | None = None,
    just_triggered: bool = False,
) -> ThreatAssessment:
    if divergence in {DivergenceState.UNDERLYING_ONLY, DivergenceState.FAILED_RESPONSE}:
        return ThreatAssessment(Threat.OPTION_DIVERGENCE, True, "option does not confirm underlying")
    risk = abs(trigger - invalidation)
    gap = abs(current - trigger)
    if risk > 0 and gap > risk:
        return ThreatAssessment(Threat.GAP_THROUGH, True, "price gapped beyond acceptable trigger distance")
    if potential_score < 35:
        return ThreatAssessment(Threat.LATE_CHASE, True, "remaining potential is too small")
    if just_triggered and ((trigger > invalidation and current <= invalidation) or
                           (trigger < invalidation and current >= invalidation)):
        return ThreatAssessment(Threat.IMMEDIATE_FAILURE, True, "trigger immediately invalidated")
    if trigger > invalidation and current < prior_extreme < trigger:
        return ThreatAssessment(Threat.FAKE_BREAKOUT, True, "breakout failed back below prior extreme")
    if trigger < invalidation and current > prior_extreme > trigger:
        return ThreatAssessment(Threat.FAKE_BREAKOUT, True, "breakdown failed back above prior extreme")
    return ThreatAssessment(Threat.NONE, False, "no adversarial threat detected")
