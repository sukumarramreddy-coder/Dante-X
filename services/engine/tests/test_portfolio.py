from dantex.portfolio import Exposure, check_correlated_exposure


def test_two_same_direction_index_bets_share_risk_bucket():
    x = check_correlated_exposure(
        existing=[Exposure("NIFTY", "india_index", 1, 700)],
        new_family="india_index", new_direction=1, new_max_loss=500,
        max_correlated_risk=1000,
    )
    assert not x.allowed
    assert x.correlated_risk == 1200
