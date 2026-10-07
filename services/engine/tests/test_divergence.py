from dantex.divergence import DivergenceState, compare_underlying_option


def test_underlying_without_option_confirmation_warns():
    result = compare_underlying_option(
        underlying_direction=1,
        option_direction=-1,
        underlying_strength=80,
        option_strength=25,
    )
    assert result.state == DivergenceState.UNDERLYING_ONLY
    assert result.warning
