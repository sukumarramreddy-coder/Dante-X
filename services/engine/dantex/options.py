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


@dataclass(frozen=True)
class StrikeIntelligence:
    contract: str
    execution_score: float
    greek_score: float
    positioning_score: float
    decay_penalty: float
    strike_score: float
    reasons: tuple[str, ...]


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


def strike_intelligence(option: OptionState, *, minutes_to_close: int) -> StrikeIntelligence:
    """Rank contract quality without changing directional probability.

    This is an execution/contract-selection score only. Direction must be
    established independently by the evidence engine.
    """
    spread_score = max(0.0, 100.0 - min(option.spread_pct * 25.0, 100.0))
    volume_score = min(100.0, option.volume / 10_000 * 100.0) if option.volume > 0 else 0.0
    oi_score = min(100.0, option.open_interest / 50_000 * 100.0) if option.open_interest > 0 else 0.0
    execution = 0.45 * spread_score + 0.30 * volume_score + 0.25 * oi_score

    delta_score = max(0.0, 100.0 - abs(abs(option.delta) - 0.50) * 200.0)
    gamma_score = min(100.0, abs(option.gamma) * 5_000.0)
    greek = 0.75 * delta_score + 0.25 * gamma_score

    oi_change_score = min(100.0, max(0.0, option.oi_change) / 10_000 * 100.0)
    positioning = 0.65 * oi_score + 0.35 * oi_change_score

    time_multiplier = 1.5 if minutes_to_close < 90 else 1.0
    decay_penalty = min(100.0, abs(option.theta) * time_multiplier)
    score = 0.45 * execution + 0.25 * greek + 0.20 * positioning + 0.10 * (100.0 - decay_penalty)

    reasons = (
        f"spread {option.spread_pct:.2f}%",
        f"delta {option.delta:.2f}",
        f"theta {option.theta:.2f}",
        f"volume {option.volume:.0f}",
        f"OI {option.open_interest:.0f}",
    )
    return StrikeIntelligence(
        contract=option.contract,
        execution_score=round(execution, 1),
        greek_score=round(greek, 1),
        positioning_score=round(positioning, 1),
        decay_penalty=round(decay_penalty, 1),
        strike_score=round(min(max(score, 0.0), 100.0), 1),
        reasons=reasons,
    )


def rank_contracts(candidates: list[OptionState], *, minutes_to_close: int) -> list[StrikeIntelligence]:
    """Best executable strike first; score is deliberately not win probability."""
    viable = [x for x in candidates if x.volume > 0 and x.open_interest > 0 and x.spread_pct <= 2.5]
    ranked = [strike_intelligence(x, minutes_to_close=minutes_to_close) for x in viable]
    return sorted(ranked, key=lambda x: x.strike_score, reverse=True)


def choose_contract(candidates: list[OptionState]) -> OptionState | None:
    """Prefer executable contracts; direction/strike merit is decided upstream."""
    viable = [x for x in candidates if x.volume > 0 and x.open_interest > 0 and x.spread_pct <= 2.5]
    if not viable:
        return None
    return max(viable, key=lambda x: (x.volume, x.open_interest, -x.spread_pct))
