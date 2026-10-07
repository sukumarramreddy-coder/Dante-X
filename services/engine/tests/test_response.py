from dantex.response import CatalystExpectation, ResponseState, classify_response


def test_bad_news_refused_by_market_is_divergent():
    result = classify_response(
        CatalystExpectation(expected_direction=-1, expected_magnitude=0.01),
        actual_return=0.004,
        related_return=0.003,
        volatility_change=-0.05,
    )
    assert result == ResponseState.DIVERGENT
