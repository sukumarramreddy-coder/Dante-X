from datetime import datetime
from zoneinfo import ZoneInfo

from dantex.authorization import ExecutionQuality
from dantex.domain import Lifecycle, Side
from dantex.features import Evidence
from dantex.path import PathCheckpoint
from dantex.pipeline import MarketObservation, evaluate_observation
from dantex.quality import DataQuality


IST = ZoneInfo("Asia/Kolkata")


def observation(usable=True):
    return MarketObservation(
        timestamp=datetime(2026, 9, 21, 12, 30, tzinfo=IST),
        symbol="NIFTY",
        price=100,
        evidence=[
            Evidence("price", 75, 25, "price"),
            Evidence("breadth", 70, 30, "breadth"),
            Evidence("option", 68, 32, "options"),
        ],
        quality=ExecutionQuality(90, 90, 80, 1.8),
        data_quality=DataQuality(usable, 0, 100 if usable else 0, "usable" if usable else "stale"),
    )


def test_full_pipeline_arms_quality_setup():
    r = evaluate_observation(
        observation(), side=Side.BULLISH, trigger=101, cancel_level=97, target=108,
        checkpoints=[PathCheckpoint(100, "above")], recent_prices=[98, 99],
    )
    assert r.status == Lifecycle.ARMED


def test_full_pipeline_fails_closed_on_bad_data():
    r = evaluate_observation(
        observation(False), side=Side.BULLISH, trigger=101, cancel_level=97, target=108,
        checkpoints=[], recent_prices=[],
    )
    assert r.status == Lifecycle.NO_EDGE
