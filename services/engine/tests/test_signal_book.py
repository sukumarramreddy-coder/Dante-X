from dantex.domain import Lifecycle, Side
from dantex.signal_book import SideState, SignalBook


def test_book_keeps_both_sides_visible():
    book = SignalBook(
        SideState(Side.BULLISH, Lifecycle.ARMED, 75, 101, 97),
        SideState(Side.BEARISH, Lifecycle.WATCH, 55, 96, 100),
    )
    assert book.active().side == Side.BULLISH
    assert book.bearish.lifecycle == Lifecycle.WATCH
