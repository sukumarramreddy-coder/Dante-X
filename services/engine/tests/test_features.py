from dantex.features import Evidence, score_hypotheses


def test_correlated_family_is_collapsed_before_scoring():
    result = score_hypotheses([
        Evidence("ema9", 90, 10, "trend"),
        Evidence("ema20", 90, 10, "trend"),
        Evidence("breadth", 60, 40, "breadth"),
        Evidence("option_response", 60, 40, "options"),
    ])
    assert result.independent_families == 3
    assert result.bullish == 70.0
