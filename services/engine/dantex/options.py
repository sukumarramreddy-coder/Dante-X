from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OptionState:
    contract: str
    timestamp: datetime
    premium: float
    bid: float
    ask: float
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float
    open_interest: float
    oi_change: float
    volume: float

    @property
    def spread_pct(self) -> float:
        mid = (self.bid + self.ask) / 2
        if mid <= 0:
            return 100.0
        return (self.ask - self.bid) / mid * 100


@dataclass(frozen=True)
class OptionResponse:
    elasticity: float
    liquidity_score: float
    decay_pressure: float
    response_score: float


def analyze_option_response(
    option: OptionState,
    *,
    premium_change_pct: float,
    underlying_change_pct: float,
    minutes_to_close: int,
) -> OptionResponse:
    denominator = abs(underlying_change_pct)
    elasticity = abs(premium_change_pct) / denominator if denominator > 1e-9 else 0.0
    spread_penalty = min(option.spread_pct * 8, 100)
    liquidity = max(0.0, 100 - spread_penalty)
    liquidity *= min(1.0, option.volume / 10_000) if option.volume > 0 else 0.0
    decay = min(100.0, abs(option.theta) * (1.5 if minutes_to_close < 90 else 1.0))
    response = min(100.0, elasticity * 20)
    return OptionResponse(round(elasticity, 2), round(liquidity, 1), round(decay, 1), round(response, 1))


def choose_contract(candidates: list[OptionState]) -> OptionState | None:
    """Prefer executable contracts; direction/strike merit is decided upstream."""
    viable = [x for x in candidates if x.volume > 0 and x.open_interest > 0 and x.spread_pct <= 2.5]
    if not viable:
        return None
    return max(viable, key=lambda x: (x.volume, x.open_interest, -x.spread_pct))
