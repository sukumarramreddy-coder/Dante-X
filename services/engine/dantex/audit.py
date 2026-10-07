from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel

from .domain import Lifecycle, Signal


class SignalEvent(BaseModel):
    timestamp: datetime
    signal_id: str
    previous: Lifecycle | None
    current: Lifecycle
    reason: str
    snapshot_hash: str | None = None


class TradeOutcome(BaseModel):
    signal_id: str
    triggered: bool
    max_favorable_excursion: float
    max_adverse_excursion: float
    estimated_slippage: float
    estimated_costs: float
    target_hit: int | None = None


class AuditRecord(BaseModel):
    signal: Signal
    events: list[SignalEvent] = []
    outcome: TradeOutcome | None = None
