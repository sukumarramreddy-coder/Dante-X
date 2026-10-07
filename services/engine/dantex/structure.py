from __future__ import annotations

from dataclasses import dataclass

from .market import Candle


@dataclass(frozen=True)
class StructureState:
    trend: str
    location_score: float
    momentum_score: float
    compression: bool
    breakout: str | None


def ema(values: list[float], period: int) -> float:
    if period <= 0 or len(values) < period:
        raise ValueError("not enough values for EMA period")
    alpha = 2 / (period + 1)
    result = sum(values[:period]) / period
    for value in values[period:]:
        result = alpha * value + (1 - alpha) * result
    return result


def atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < period + 1:
        raise ValueError("not enough candles for ATR")
    ranges = []
    for previous, current in zip(candles[-period - 1:-1], candles[-period:]):
        ranges.append(max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        ))
    return sum(ranges) / period


def analyze_structure(candles: list[Candle]) -> StructureState:
    if len(candles) < 21:
        raise ValueError("at least 21 candles required")
    closes = [c.close for c in candles]
    fast, slow = ema(closes, 9), ema(closes, 20)
    last = candles[-1]
    trend = "bullish" if last.close > fast > slow else "bearish" if last.close < fast < slow else "mixed"
    recent = candles[-10:]
    avg_range = sum(c.range() for c in recent[:-1]) / 9
    compression = last.range() < avg_range * 0.65 if avg_range else False
    prior_high = max(c.high for c in candles[-6:-1])
    prior_low = min(c.low for c in candles[-6:-1])
    breakout = "up" if last.close > prior_high else "down" if last.close < prior_low else None
    distance = (last.close - slow) / slow * 100
    location = min(100.0, max(0.0, 50 + distance * 10))
    momentum = 70.0 if breakout else 60.0 if trend != "mixed" else 45.0
    return StructureState(trend, round(location, 1), momentum, compression, breakout)
