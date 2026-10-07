from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ResponseState(StrEnum):
    ACCEPTED = "accepted"
    ABSORBED = "absorbed"
    DIVERGENT = "divergent"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class CatalystExpectation:
    expected_direction: int  # -1 bearish, +1 bullish
    expected_magnitude: float


def classify_response(
    expectation: CatalystExpectation,
    *,
    actual_return: float,
    related_return: float,
    volatility_change: float,
    tolerance: float = 0.001,
) -> ResponseState:
    """Expected-vs-actual response: a catalyst is evidence only if price accepts it."""
    if expectation.expected_direction not in (-1, 1):
        raise ValueError("expected_direction must be -1 or +1")

    signed_actual = actual_return * expectation.expected_direction
    signed_related = related_return * expectation.expected_direction

    if signed_actual > tolerance and signed_related > -tolerance:
        return ResponseState.ACCEPTED
    if signed_actual < -tolerance and signed_related < -tolerance:
        return ResponseState.DIVERGENT
    if abs(actual_return) <= tolerance or volatility_change < 0:
        return ResponseState.ABSORBED
    return ResponseState.INCONCLUSIVE
