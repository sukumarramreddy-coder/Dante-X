from dantex.performance import TradeOutcome, summarize_performance
from dantex.positioning import positioning_snapshot


def test_positioning_exposes_pcr_walls_and_counterweights():
    rows = [
        {"strike": 23400, "call": {"oi": 100, "oi_change": 10}, "put": {"oi": 400, "oi_change": 80}},
        {"strike": 23500, "call": {"oi": 500, "oi_change": 20}, "put": {"oi": 100, "oi_change": 10}},
    ]
    x = positioning_snapshot(rows, spot=23450)
    assert x.pcr_oi is not None
    assert x.call_wall == 23500
    assert x.put_wall == 23400
    assert len(x.counterweights) == 2


def test_performance_summary_tracks_expectancy_and_excursions():
    s = summarize_performance([
        TradeOutcome(result_r=2.0, mfe_r=2.4, mae_r=0.3, costs_r=0.1),
        TradeOutcome(result_r=-1.0, mfe_r=0.2, mae_r=1.0, costs_r=0.1),
    ])
    assert s.trades == 2
    assert s.win_rate == 50.0
    assert s.expectancy_r == 0.4
    assert s.profit_factor is not None
    assert s.avg_mfe_r == 1.3
