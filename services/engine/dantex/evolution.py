from __future__ import annotations

from dataclasses import dataclass

from .domain import Side


@dataclass(frozen=True)
class ScorePoint:
    sequence: int
    bullish: float
    bearish: float


@dataclass(frozen=True)
class Evolution:
    bullish_delta: float
    bearish_delta: float
    takeover: Side | None


def analyze_evolution(points: list[ScorePoint], *, takeover_margin: float = 15) -> Evolution:
    if len(points) < 2:
        return Evolution(0, 0, None)
    first, last = points[0], points[-1]
    bull_delta = last.bullish - first.bullish
    bear_delta = last.bearish - first.bearish
    takeover = None
    if last.bullish - last.bearish >= takeover_margin and bull_delta > 0 and bear_delta < 0:
        takeover = Side.BULLISH
    elif last.bearish - last.bullish >= takeover_margin and bear_delta > 0 and bull_delta < 0:
        takeover = Side.BEARISH
    return Evolution(bull_delta, bear_delta, takeover)
