from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .adversarial import ThreatAssessment, assess_threat
from .authorization import ExecutionQuality
from .divergence import DivergenceState
from .domain import Lifecycle, Side
from .features import Evidence
from .orchestrator import Decision, SetupCandidate, evaluate_candidate
from .path import PathCheckpoint
from .potential import Potential, potential_left
from .quality import DataQuality
from .session import intraday_session_status


@dataclass(frozen=True)
class MarketObservation:
    timestamp: datetime
    symbol: str
    price: float
    evidence: list[Evidence]
    quality: ExecutionQuality
    data_quality: DataQuality


@dataclass(frozen=True)
class PipelineResult:
    decision: Decision | None
    status: Lifecycle
    reason: str
    threat: ThreatAssessment | None = None
    potential: Potential | None = None


def evaluate_observation(
    observation: MarketObservation,
    *,
    side: Side,
    trigger: float,
    cancel_level: float,
    target: float,
    checkpoints: list[PathCheckpoint],
    recent_prices: list[float],
    prior_extreme: float | None = None,
    divergence: DivergenceState | None = None,
    estimated_cost_distance: float = 0,
) -> PipelineResult:
    if not observation.data_quality.usable:
        return PipelineResult(None, Lifecycle.NO_EDGE, observation.data_quality.reason)
    session = intraday_session_status(observation.timestamp)
    if session != "entry_allowed":
        return PipelineResult(None, Lifecycle.NO_EDGE, f"intraday session: {session}")

    potential = potential_left(
        current=observation.price,
        target=target,
        invalidation=cancel_level,
        estimated_cost_distance=estimated_cost_distance,
    )
    threat = assess_threat(
        trigger=trigger,
        current=observation.price,
        invalidation=cancel_level,
        prior_extreme=prior_extreme if prior_extreme is not None else observation.price,
        potential_score=potential.score,
        divergence=divergence,
    )
    if threat.block_entry:
        return PipelineResult(None, Lifecycle.NO_EDGE, threat.reason, threat, potential)
    if not potential.worthwhile:
        return PipelineResult(
            None, Lifecycle.NO_EDGE, "insufficient potential after risk and costs", threat, potential
        )

    candidate = SetupCandidate(
        symbol=observation.symbol,
        side=side,
        trigger=trigger,
        cancel_level=cancel_level,
        target=target,
        evidence=observation.evidence,
        path=checkpoints,
        quality=observation.quality,
    )
    decision = evaluate_candidate(
        candidate,
        prices=recent_prices + [observation.price],
        timestamp=observation.timestamp,
    )
    return PipelineResult(
        decision, decision.lifecycle, decision.authorization.reason, threat, potential
    )
