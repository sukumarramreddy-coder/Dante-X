from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PathCheckpoint:
    level: float
    direction: str  # "above" or "below"


@dataclass(frozen=True)
class PathProgress:
    matched: int
    total: int
    score: float
    next_level: float | None


def evaluate_path(checkpoints: list[PathCheckpoint], prices: list[float]) -> PathProgress:
    if not checkpoints:
        return PathProgress(0, 0, 0.0, None)
    matched = 0
    cursor = 0
    for checkpoint in checkpoints:
        found = False
        while cursor < len(prices):
            p = prices[cursor]
            cursor += 1
            if (checkpoint.direction == "above" and p >= checkpoint.level) or (
                checkpoint.direction == "below" and p <= checkpoint.level
            ):
                found = True
                break
        if not found:
            break
        matched += 1
    score = matched / len(checkpoints) * 100
    next_level = checkpoints[matched].level if matched < len(checkpoints) else None
    return PathProgress(matched, len(checkpoints), round(score, 1), next_level)
