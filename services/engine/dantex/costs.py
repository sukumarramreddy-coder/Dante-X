from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostEstimate:
    brokerage: float
    taxes_and_fees: float
    slippage: float

    @property
    def total(self) -> float:
        return round(self.brokerage + self.taxes_and_fees + self.slippage, 2)


def conservative_cost_estimate(
    *,
    quantity: int,
    entry: float,
    exit: float,
    brokerage: float,
    fee_rate: float,
    slippage_bps: float,
) -> CostEstimate:
    turnover = quantity * (entry + exit)
    fees = turnover * fee_rate
    slippage = turnover * slippage_bps / 10_000
    return CostEstimate(round(brokerage, 2), round(fees, 2), round(slippage, 2))
