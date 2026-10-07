from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Potential:
    score: float
    remaining_move: float
    risk_distance: float
    worthwhile: bool


def potential_left(
    *,
    current: float,
    target: float,
    invalidation: float,
    estimated_cost_distance: float = 0,
    minimum_reward_to_risk: float = 1.3,
) -> Potential:
    reward = abs(target - current) - estimated_cost_distance
    risk = abs(current - invalidation) + estimated_cost_distance
    if risk <= 0:
        return Potential(0, max(0, reward), risk, False)
    ratio = max(0, reward) / risk
    score = min(100.0, ratio / 3 * 100)
    return Potential(round(score, 1), round(max(0, reward), 4), round(risk, 4), ratio >= minimum_reward_to_risk)
