from dantex.regime import Regime, classify_regime


def test_compression_takes_priority():
    assert classify_regime(atr_pct=0.5, trend_strength=40, compression=80).regime == Regime.COMPRESSION


def test_strong_direction_is_trend():
    assert classify_regime(atr_pct=0.8, trend_strength=75, compression=20).regime == Regime.TREND
