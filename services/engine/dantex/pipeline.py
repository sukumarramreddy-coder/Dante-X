from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .authorization import ExecutionQuality
from .domain import Lifecycle, Side
from .features import Evidence
from .orchestrator import Decision, SetupCandidate, evaluate_candidate
from .path import PathCheckpoint
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


def evaluate_observation(
    observation: MarketObservation,
    *,
    side: Side,
    trigger: float,
    cancel_level: float,
    target: float,
    checkpoints: list[PathCheckpoint],
    recent_prices: list[float],
) -> PipelineResult:
    if not observation.data_quality.usable:
        return PipelineResult(None, Lifecycle.NO_EDGE, observation.data_quality.reason)
    session = intraday_session_status(observation.timestamp)
    if session != "entry_allowed":
        return PipelineResult(None, Lifecycle.NO_EDGE, f"intraday session: {session}")
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
    return PipelineResult(decision, decision.lifecycle, decision.authorization.reason)
