from dantex.domain import Lifecycle, Side
from dantex.management import manage_open_trade


def test_does_not_widen_failed_stop():
    x = manage_open_trade(
        side=Side.BULLISH, current=97, stop=98, target1=108, target2=112,
        path_score=80, option_confirming=True,
    )
    assert x.lifecycle == Lifecycle.EXIT


def test_option_divergence_warns_before_structural_stop():
    x = manage_open_trade(
        side=Side.BULLISH, current=103, stop=98, target1=108, target2=112,
        path_score=70, option_confirming=False,
    )
    assert x.lifecycle == Lifecycle.WARNING


def test_strong_move_can_run_beyond_t2():
    x = manage_open_trade(
        side=Side.BULLISH, current=113, stop=98, target1=108, target2=112,
        path_score=90, option_confirming=True,
    )
    assert x.lifecycle == Lifecycle.RUN
