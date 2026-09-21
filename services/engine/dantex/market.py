from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from .domain import AssetClass


class Quote(BaseModel):
    symbol: str
    asset_class: AssetClass
    timestamp: datetime
    last: float = Field(gt=0)
    bid: float | None = Field(default=None, gt=0)
    ask: float | None = Field(default=None, gt=0)
    volume: float | None = Field(default=None, ge=0)
    open_interest: float | None = Field(default=None, ge=0)

    @property
    def spread_bps(self) -> float | None:
        if self.bid is None or self.ask is None:
            return None
        mid = (self.bid + self.ask) / 2
        return round((self.ask - self.bid) / mid * 10_000, 2)


class Candle(BaseModel):
    symbol: str
    timestamp: datetime
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0)

    def range(self) -> float:
        return self.high - self.low


class MarketSnapshot(BaseModel):
    timestamp: datetime
    underlying: Quote
    related: list[Quote] = []
    vix: Quote | None = None
    breadth_advance_pct: float | None = Field(default=None, ge=0, le=100)
    catalyst_tags: list[str] = []
