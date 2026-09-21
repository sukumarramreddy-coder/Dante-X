from dantex.domain import Side
from dantex.features import HypothesisScore
from dantex.flip import evaluate_flip


def test_flip_requires_strong_opposite_takeover():
    h = HypothesisScore(bullish=25, bearish=75, conflict=25, independent_families=5)
    result = evaluate_flip(Side.BULLISH, h)
    assert result.flip
    assert result.new_side == Side.BEARISH


def test_does_not_flip_on_noise():
    h = HypothesisScore(bullish=48, bearish=52, conflict=48, independent_families=4)
    assert not evaluate_flip(Side.BULLISH, h).flip
