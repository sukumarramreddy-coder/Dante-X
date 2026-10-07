from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ..market import MarketSnapshot, Quote


class MarketDataProvider(ABC):
    """Read-only provider boundary. No order methods belong here."""

    @abstractmethod
    async def quote(self, symbol: str) -> Quote:
        raise NotImplementedError

    @abstractmethod
    async def snapshot(self, symbol: str) -> MarketSnapshot:
        raise NotImplementedError

    @abstractmethod
    async def stream(self, symbols: list[str]) -> AsyncIterator[Quote]:
        raise NotImplementedError
