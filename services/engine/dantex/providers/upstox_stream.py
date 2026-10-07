from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class FeedMode(StrEnum):
    LTPC = "ltpc"
    OPTION_GREEKS = "option_greeks"
    FULL = "full"
    FULL_D30 = "full_d30"


@dataclass(frozen=True)
class Subscription:
    instrument_keys: tuple[str, ...]
    mode: FeedMode = FeedMode.FULL

    def request(self, guid: str, method: str = "sub") -> bytes:
        if not self.instrument_keys:
            raise ValueError("at least one instrument key is required")
        return json.dumps({
            "guid": guid,
            "method": method,
            "data": {"mode": self.mode.value, "instrumentKeys": list(self.instrument_keys)},
        }).encode()


@dataclass
class FeedHealth:
    last_message_at: datetime | None = None
    reconnects: int = 0
    market_status_seen: bool = False
    snapshot_seen: bool = False
    _sequence: int = field(default=0, repr=False)

    def observe(self, message_type: str, at: datetime | None = None) -> None:
        self.last_message_at = at or datetime.now(timezone.utc)
        self._sequence += 1
        if message_type == "market_info":
            self.market_status_seen = True
        elif message_type == "live_feed" and self.market_status_seen:
            self.snapshot_seen = True

    def stale(self, now: datetime, *, max_age_seconds: float = 5) -> bool:
        if self.last_message_at is None:
            return True
        return (now - self.last_message_at).total_seconds() > max_age_seconds

    @property
    def synchronized(self) -> bool:
        return self.market_status_seen and self.snapshot_seen


def decode_with(decoder: Any, payload: bytes) -> Any:
    """Decode Upstox protobuf bytes using an injected generated protobuf decoder."""
    if not payload:
        raise ValueError("empty websocket payload")
    return decoder(payload)
