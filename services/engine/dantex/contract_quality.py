from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractQuality:
    executable: bool
    score: float
    reason: str


def assess_contract(
    *,
    bid: float,
    ask: float,
    volume: int,
    open_interest: int,
    min_volume: int = 100,
    min_open_interest: int = 500,
    max_spread_pct: float = 2.5,
) -> ContractQuality:
    if bid <= 0 or ask <= 0 or ask < bid:
        return ContractQuality(False, 0, "invalid bid/ask")
    mid = (bid + ask) / 2
    spread_pct = (ask - bid) / mid * 100
    if volume < min_volume:
        return ContractQuality(False, 0, "insufficient volume")
    if open_interest < min_open_interest:
        return ContractQuality(False, 0, "insufficient open interest")
    if spread_pct > max_spread_pct:
        return ContractQuality(False, 0, "spread too wide")
    liquidity = min(100, volume / min_volume * 35 + open_interest / min_open_interest * 35)
    spread_component = max(0, 30 * (1 - spread_pct / max_spread_pct))
    return ContractQuality(True, round(min(100, liquidity + spread_component), 1), "executable")
