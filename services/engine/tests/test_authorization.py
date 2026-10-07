from dantex.authorization import ExecutionQuality, authorize
from dantex.features import HypothesisScore


def test_blocks_spent_move_even_with_strong_direction():
    h = HypothesisScore(bullish=80, bearish=20, conflict=20, independent_families=5)
    q = ExecutionQuality(liquidity=90, spread=90, potential_left=20, net_r_multiple=2)
    result = authorize(h, q)
    assert not result.allowed
    assert "spent" in result.reason


def test_authorizes_executable_asymmetry():
    h = HypothesisScore(bullish=72, bearish=28, conflict=28, independent_families=4)
    q = ExecutionQuality(liquidity=85, spread=80, potential_left=70, net_r_multiple=1.8)
    assert authorize(h, q).allowed
