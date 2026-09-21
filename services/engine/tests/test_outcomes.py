from dantex.domain import Side
from dantex.outcomes import measure_excursion


def test_bullish_excursion_records_mfe_mae_and_targets():
    x = measure_excursion(
        side=Side.BULLISH, entry=100, stop=95, target1=106, target2=110,
        prices=[99, 103, 107, 102],
    )
    assert x.mfe == 7
    assert x.mae == 1
    assert x.target1_hit
    assert not x.target2_hit
    assert not x.stop_hit
