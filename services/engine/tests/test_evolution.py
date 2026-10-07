from dantex.domain import Side
from dantex.evolution import ScorePoint, analyze_evolution


def test_bearish_takeover_requires_opposite_score_motion():
    x = analyze_evolution([
        ScorePoint(1, 72, 40),
        ScorePoint(2, 60, 55),
        ScorePoint(3, 45, 72),
    ])
    assert x.takeover == Side.BEARISH
    assert x.bearish_delta > 0
    assert x.bullish_delta < 0
