from dantex.reaction import Reaction, assess_reaction
from dantex.score_adjust import apply_reaction


def test_bad_news_refusal_strengthens_bullish_hypothesis():
    r = assess_reaction(
        expected_direction=-1, actual_return=0.35, breadth_change=12, volatility_change=-0.4,
    )
    assert r.reaction == Reaction.REFUSED
    scores = apply_reaction(bullish=52, bearish=68, reaction=r)
    assert scores.bullish > 52
    assert scores.bearish < 68


def test_good_news_refusal_strengthens_bearish_hypothesis():
    r = assess_reaction(
        expected_direction=1, actual_return=-0.3, breadth_change=-10, volatility_change=0.5,
    )
    assert r.reaction == Reaction.REFUSED
    scores = apply_reaction(bullish=68, bearish=45, reaction=r)
    assert scores.bullish < 68
    assert scores.bearish > 45
