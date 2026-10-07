from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone

from .base import MarketDataProvider
from ..domain import AssetClass
from ..market import MarketSnapshot, Quote


class MockProvider(MarketDataProvider):
    """Deterministic development provider. Never represented as live market data."""

    async def quote(self, symbol: str) -> Quote:
        return Quote(
            symbol=symbol,
            asset_class=AssetClass.INDEX,
            timestamp=datetime.now(timezone.utc),
            last=100.0,
            bid=99.95,
            ask=100.05,
            volume=1_000_000,
        )

    async def snapshot(self, symbol: str) -> MarketSnapshot:
        return MarketSnapshot(timestamp=datetime.now(timezone.utc), underlying=await self.quote(symbol))

    async def stream(self, symbols: list[str]) -> AsyncIterator[Quote]:
        for symbol in symbols:
            yield await self.quote(symbol)
