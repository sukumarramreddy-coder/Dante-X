from __future__ import annotations

from dataclasses import dataclass

from .radar import RadarInputs, opportunity_score


@dataclass(frozen=True)
class RadarCandidate:
    symbol: str
    asset_class: str
    side: str
    inputs: RadarInputs
    executable: bool
    block_reason: str | None = None


@dataclass(frozen=True)
class RankedCandidate:
    rank: int
    symbol: str
    asset_class: str
    side: str
    score: float
    status: str
    reason: str | None


def rank_candidates(candidates: list[RadarCandidate]) -> list[RankedCandidate]:
    scored = []
    for candidate in candidates:
        score = opportunity_score(candidate.inputs) if candidate.executable else 0.0
        scored.append((score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        RankedCandidate(
            rank=i,
            symbol=c.symbol,
            asset_class=c.asset_class,
            side=c.side,
            score=score,
            status="eligible" if c.executable else "blocked",
            reason=c.block_reason,
        )
        for i, (score, c) in enumerate(scored, start=1)
    ]
