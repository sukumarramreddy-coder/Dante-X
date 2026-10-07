from dantex.domain import Side
from dantex.duel import DuelStatus, Thesis, resolve_duel


def thesis(side, score, executable=True):
    return Thesis(side, score, executable, 70, 70)


def test_conflicting_strong_sides_do_not_force_trade():
    x = resolve_duel(thesis(Side.BULLISH, 72), thesis(Side.BEARISH, 68))
    assert x.status == DuelStatus.CONFLICT
    assert x.leader is None


def test_clear_bullish_asymmetry_can_lead():
    x = resolve_duel(thesis(Side.BULLISH, 78), thesis(Side.BEARISH, 61))
    assert x.leader == Side.BULLISH


def test_unexecutable_high_score_cannot_win():
    x = resolve_duel(thesis(Side.BULLISH, 90, False), thesis(Side.BEARISH, 70))
    assert x.leader == Side.BEARISH
