"""Frozen Dante X Knowledge Transfer v1.0 policy contract.

This module is intentionally declarative. It records permanent reasoning and safety
invariants that other engine components may reference without turning conversational
history into runtime prompts or permitting self-modification.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


KT_VERSION = "1.0-frozen"


class OperatorAction(StrEnum):
    WAIT = "WAIT"
    GO = "GO"
    HOLD = "HOLD"
    PROTECT = "PROTECT"
    EXIT = "EXIT"


class EvidenceDomain(StrEnum):
    PRICE_STRUCTURE = "price_structure"
    MULTI_TIMEFRAME = "multi_timeframe"
    LIQUIDITY = "liquidity"
    DERIVATIVES = "derivatives"
    CROSS_MARKET = "cross_market"
    EXTERNAL_CONTEXT = "external_context"
    OPPORTUNITY = "opportunity"
    EXECUTION_QUALITY = "execution_quality"
    TRADE_MANAGEMENT = "trade_management"
    OUTCOME = "outcome"


@dataclass(frozen=True)
class FrozenKnowledgePolicy:
    read_only: bool = True
    maintain_competing_sides: bool = True
    separate_direction_from_instrument: bool = True
    structural_invalidation_before_quantity: bool = True
    net_risk_reward_required: bool = True
    intraday_must_exit_same_day: bool = True
    preserve_failures: bool = True
    preserve_rejected_setups: bool = True
    historical_and_forward_evidence_separate: bool = True
    calibrated_probability_requires_validation: bool = True
    self_adaptation_during_initial_calibration: bool = False
    synthetic_evidence_may_unlock_calibration: bool = False
    execution_enabled: bool = False


FROZEN_POLICY = FrozenKnowledgePolicy()

# Ordering is a reasoning priority, not a numeric probability model. External events
# provide context; observed market response and executable evidence remain authoritative.
EVIDENCE_PRIORITY = (
    EvidenceDomain.PRICE_STRUCTURE,
    EvidenceDomain.MULTI_TIMEFRAME,
    EvidenceDomain.LIQUIDITY,
    EvidenceDomain.DERIVATIVES,
    EvidenceDomain.CROSS_MARKET,
    EvidenceDomain.OPPORTUNITY,
    EvidenceDomain.EXECUTION_QUALITY,
    EvidenceDomain.EXTERNAL_CONTEXT,
    EvidenceDomain.TRADE_MANAGEMENT,
    EvidenceDomain.OUTCOME,
)

# Historical bootstrap, forward observation, and calibration are deliberately distinct.
CALIBRATION_STAGES = (
    "historical_bootstrap",
    "forward_observation",
    "out_of_sample_validation",
    "calibration_gate",
)

# Checkpoints are review opportunities, never automatic permission to publish probability.
REVIEW_SESSION_CHECKPOINTS = (30, 60, 90)
