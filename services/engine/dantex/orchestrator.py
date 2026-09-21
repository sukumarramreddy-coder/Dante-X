from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .authorization import Authorization, ExecutionQuality, authorize
from .domain import Lifecycle, Side
from .features import Evidence, HypothesisScore, score_hypotheses
from .path import PathCheckpoint, PathProgress, evaluate_path


@dataclass(frozen=True)
class SetupCandidate:
    symbol: str
    side: Side
    trigger: float
    cancel_level: float
    target: float
    evidence: list[Evidence]
    path: list[PathCheckpoint]
    quality: ExecutionQuality


@dataclass(frozen=True)
class Decision:
    timestamp: datetime
    symbol: str
    side: Side
    lifecycle: Lifecycle
    hypothesis: HypothesisScore
    path: PathProgress
    authorization: Authorization
    trigger: float
    cancel_level: float
    target: float


def evaluate_candidate(
    candidate: SetupCandidate,
    *,
    prices: list[float],
    timestamp: datetime,
) -> Decision:
    hypothesis = score_hypotheses(candidate.evidence)
    path = evaluate_path(candidate.path, prices)
    auth = authorize(hypothesis, candidate.quality)
    lifecycle = Lifecycle.ARMED if auth.allowed else Lifecycle.WATCH
    return Decision(
        timestamp=timestamp,
        symbol=candidate.symbol,
        side=candidate.side,
        lifecycle=lifecycle,
        hypothesis=hypothesis,
        path=path,
        authorization=auth,
        trigger=candidate.trigger,
        cancel_level=candidate.cancel_level,
        target=candidate.target,
    )


def advance_armed(decision: Decision, current_price: float) -> Lifecycle:
    """ARMED is stable: only trigger or cancel changes it."""
    if decision.side == Side.BULLISH:
        if current_price <= decision.cancel_level:
            return Lifecycle.CANCEL
        if current_price >= decision.trigger:
            return Lifecycle.GO
    else:
        if current_price >= decision.cancel_level:
            return Lifecycle.CANCEL
        if current_price <= decision.trigger:
            return Lifecycle.GO
    return Lifecycle.ARMED
