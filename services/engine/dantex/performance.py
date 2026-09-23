from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeOutcome:
    result_r: float
    mfe_r: float
    mae_r: float
    costs_r: float = 0.0


@dataclass(frozen=True)
class PerformanceSummary:
    trades: int
    win_rate: float | None
    expectancy_r: float | None
    profit_factor: float | None
    avg_win_r: float | None
    avg_loss_r: float | None
    avg_mfe_r: float | None
    avg_mae_r: float | None


def summarize_performance(outcomes: list[TradeOutcome]) -> PerformanceSummary:
    """Summarize labelled SHADOW outcomes. No calibration claim is implied."""
    if not outcomes:
        return PerformanceSummary(0, None, None, None, None, None, None, None)
    net = [x.result_r - x.costs_r for x in outcomes]
    wins = [x for x in net if x > 0]
    losses = [x for x in net if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return PerformanceSummary(
        trades=len(outcomes),
        win_rate=round(len(wins) / len(outcomes) * 100, 1),
        expectancy_r=round(sum(net) / len(net), 3),
        profit_factor=round(gross_profit / gross_loss, 3) if gross_loss else None,
        avg_win_r=round(sum(wins) / len(wins), 3) if wins else None,
        avg_loss_r=round(sum(losses) / len(losses), 3) if losses else None,
        avg_mfe_r=round(sum(x.mfe_r for x in outcomes) / len(outcomes), 3),
        avg_mae_r=round(sum(x.mae_r for x in outcomes) / len(outcomes), 3),
    )
