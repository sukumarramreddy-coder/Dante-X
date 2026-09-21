from __future__ import annotations

from dataclasses import dataclass

from .domain import Side


@dataclass(frozen=True)
class Excursion:
    mfe: float
    mae: float
    target1_hit: bool
    target2_hit: bool
    stop_hit: bool


def measure_excursion(
    *,
    side: Side,
    entry: float,
    stop: float,
    target1: float,
    target2: float,
    prices: list[float],
) -> Excursion:
    if not prices:
        return Excursion(0, 0, False, False, False)
    if side == Side.BULLISH:
        favorable = max(prices) - entry
        adverse = entry - min(prices)
        return Excursion(
            max(0, favorable), max(0, adverse),
            max(prices) >= target1, max(prices) >= target2, min(prices) <= stop,
        )
    favorable = entry - min(prices)
    adverse = max(prices) - entry
    return Excursion(
        max(0, favorable), max(0, adverse),
        min(prices) <= target1, min(prices) <= target2, max(prices) >= stop,
    )
