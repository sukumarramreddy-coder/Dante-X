from dantex.gap import validate_gap


def test_large_gap_does_not_convert_trigger_to_market_chase():
    assert not validate_gap(trigger=100, observed=106, max_distance=2).executable


def test_small_gap_can_remain_executable():
    assert validate_gap(trigger=100, observed=101, max_distance=2).executable
