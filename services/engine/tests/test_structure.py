from datetime import UTC, datetime, timedelta

from dantex.market import Candle
from dantex.structure import analyze_structure, atr, ema


def candles():
    now = datetime.now(UTC)
    return [
        Candle(
            symbol="TEST",
            timestamp=now + timedelta(minutes=i),
            interval="1m",
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100.5 + i,
            volume=1000,
        )
        for i in range(30)
    ]


def test_ema_and_atr_are_deterministic():
    data = candles()
    assert ema([c.close for c in data], 9) > 0
    assert atr(data) > 0


def test_structure_detects_uptrend():
    state = analyze_structure(candles())
    assert state.trend == "bullish"
