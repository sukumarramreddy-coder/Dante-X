from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CircuitState:
    trading_allowed: bool
    remaining_loss_budget: float
    reason: str


def daily_loss_circuit(
    *,
    realized_pnl: float,
    open_risk: float,
    max_daily_loss: float,
) -> CircuitState:
    consumed = max(0.0, -realized_pnl) + max(0.0, open_risk)
    remaining = max(0.0, max_daily_loss - consumed)
    if remaining <= 0:
        return CircuitState(False, 0.0, "daily loss circuit reached")
    return CircuitState(True, round(remaining, 2), "risk budget available")
