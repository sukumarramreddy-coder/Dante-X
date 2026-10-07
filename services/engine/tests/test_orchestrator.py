from datetime import UTC, datetime

from dantex.authorization import ExecutionQuality
from dantex.domain import Lifecycle, Side
from dantex.features import Evidence
from dantex.orchestrator import SetupCandidate, advance_armed, evaluate_candidate
from dantex.path import PathCheckpoint


def candidate():
    return SetupCandidate(
        symbol="NIFTY",
        side=Side.BULLISH,
        trigger=101,
        cancel_level=97,
        target=108,
        evidence=[
            Evidence("structure", 75, 25, "price"),
            Evidence("breadth", 70, 30, "breadth"),
            Evidence("option", 65, 35, "options"),
        ],
        path=[PathCheckpoint(100, "above"), PathCheckpoint(101, "above")],
        quality=ExecutionQuality(90, 90, 80, 1.8),
    )


def test_candidate_arms_before_trigger():
    d = evaluate_candidate(candidate(), prices=[98, 100], timestamp=datetime.now(UTC))
    assert d.lifecycle == Lifecycle.ARMED
    assert advance_armed(d, 100.9) == Lifecycle.ARMED
    assert advance_armed(d, 101) == Lifecycle.GO


def test_armed_setup_cancels_without_moving_trigger():
    d = evaluate_candidate(candidate(), prices=[98, 100], timestamp=datetime.now(UTC))
    assert advance_armed(d, 97) == Lifecycle.CANCEL
    assert d.trigger == 101
