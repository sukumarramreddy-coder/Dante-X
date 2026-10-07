from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MarketPulse:
    """Compact operator/app contract; descriptive, never trade authorization."""

    symbol: str
    spot: float | None
    structure: str
    option_response: str
    positioning: str
    breadth: str
    volatility: str
    counterweights: tuple[str, ...]
    freshness: str


def _state(value: Any, default: str = "UNAVAILABLE") -> str:
    if isinstance(value, dict):
        return str(value.get("state") or value.get("classification") or default)
    return default


def build_market_pulse(
    *,
    symbol: str,
    spot: float | None,
    structure: dict[str, Any],
    options: dict[str, Any],
    breadth: dict[str, Any],
    volatility: dict[str, Any],
    freshness: dict[str, Any],
    counterweights: list[str] | tuple[str, ...] = (),
) -> MarketPulse:
    """Normalize the engine evidence into a stable mobile/web presentation model."""
    positioning = options.get("positioning") or {}
    path = options.get("path_response") or {}
    fresh = "LIVE" if freshness.get("eligible") else "BLOCKED"
    return MarketPulse(
        symbol=symbol,
        spot=spot,
        structure=_state(structure),
        option_response=_state(path),
        positioning=_state(positioning, "DESCRIPTIVE_ONLY"),
        breadth=_state(breadth),
        volatility=_state(volatility),
        counterweights=tuple(counterweights),
        freshness=fresh,
    )
