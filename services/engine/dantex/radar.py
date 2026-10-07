from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RadarInputs:
    live_confirmation: float
    path_match: float
    potential_left: float
    net_r_multiple: float
    liquidity_score: float
    spread_score: float


def opportunity_score(x: RadarInputs) -> float:
    """Ranking score, deliberately NOT a win probability."""
    rr = min(max(x.net_r_multiple / 3.0 * 100, 0), 100)
    score = (
        0.25 * x.live_confirmation
        + 0.20 * x.path_match
        + 0.20 * x.potential_left
        + 0.15 * rr
        + 0.12 * x.liquidity_score
        + 0.08 * x.spread_score
    )
    return round(min(max(score, 0), 100), 1)
