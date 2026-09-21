from dantex.domain import Side
from dantex.takeover import authorize_takeover


def test_bearish_takeover_requires_independent_authorization():
    x = authorize_takeover(
        cancelled_side=Side.BULLISH, bullish_score=25, bearish_score=78,
        opposite_executable=True,
    )
    assert x.authorized
    assert x.side == Side.BEARISH


def test_no_revenge_flip_into_bad_instrument():
    x = authorize_takeover(
        cancelled_side=Side.BULLISH, bullish_score=20, bearish_score=90,
        opposite_executable=False,
    )
    assert not x.authorized
