from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DivergenceState(StrEnum):
    CONFIRMED = "confirmed"
    UNDERLYING_ONLY = "underlying_only"
    OPTION_ONLY = "option_only"
    FAILED_RESPONSE = "failed_response"


@dataclass(frozen=True)
class DivergenceResult:
    state: DivergenceState
    score: float
    warning: str | None


def compare_underlying_option(
    *,
    underlying_direction: int,
    option_direction: int,
    underlying_strength: float,
    option_strength: float,
) -> DivergenceResult:
    if underlying_direction not in (-1, 1) or option_direction not in (-1, 1):
        raise ValueError("directions must be -1 or +1")
    if underlying_direction == option_direction:
        score = min(100.0, (underlying_strength + option_strength) / 2)
        return DivergenceResult(DivergenceState.CONFIRMED, round(score, 1), None)
    if underlying_strength >= 60 and option_strength < 40:
        return DivergenceResult(
            DivergenceState.UNDERLYING_ONLY,
            round(underlying_strength - option_strength, 1),
            "Underlying thesis is not being confirmed by the option.",
        )
    if option_strength >= 60 and underlying_strength < 40:
        return DivergenceResult(
            DivergenceState.OPTION_ONLY,
            round(option_strength - underlying_strength, 1),
            "Option is moving without adequate underlying confirmation.",
        )
    return DivergenceResult(
        DivergenceState.FAILED_RESPONSE,
        round(abs(underlying_strength - option_strength), 1),
        "Underlying and option response conflict.",
    )
