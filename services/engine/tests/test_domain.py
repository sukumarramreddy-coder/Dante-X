import pytest
from dantex.domain import Confidence


def test_uncalibrated_model_cannot_publish_probability():
    with pytest.raises(ValueError):
        Confidence(
            live_confirmation=70,
            path_match=60,
            potential_left=80,
            calibrated_probability=72,
        )
