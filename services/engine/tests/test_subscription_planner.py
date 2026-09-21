from dantex.providers.subscription_planner import FeedLimits, plan_subscriptions
from dantex.providers.upstox_stream import FeedMode


def test_focus_gets_full_and_radar_gets_cheaper_feed():
    x = plan_subscriptions(
        radar_keys=["A", "B", "C"], focus_keys=["A"], option_keys=["O1", "O2"],
        limits=FeedLimits(ltpc=10, option_greeks=10, full=10, combined=10),
    )
    assert x[0].mode == FeedMode.FULL
    assert x[0].instrument_keys == ("A",)
    assert x[-1].mode == FeedMode.LTPC
    assert "A" not in x[-1].instrument_keys


def test_combined_limit_is_never_exceeded():
    x = plan_subscriptions(
        radar_keys=[f"R{i}" for i in range(10)],
        focus_keys=["F1", "F2"], option_keys=["O1", "O2", "O3"],
        limits=FeedLimits(ltpc=10, option_greeks=10, full=10, combined=4),
    )
    assert sum(len(s.instrument_keys) for s in x) <= 4
