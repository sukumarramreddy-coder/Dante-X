from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .provider_state import ProviderState, ProviderStatus, transition
from .upstox_stream import FeedHealth


@dataclass
class ProviderRuntime:
    status: ProviderStatus
    health: FeedHealth

    @classmethod
    def offline(cls) -> "ProviderRuntime":
        now = datetime.now(timezone.utc)
        return cls(ProviderStatus(ProviderState.OFFLINE, now, "not connected"), FeedHealth())

    def begin_connect(self, at: datetime) -> None:
        self.status = transition(self.status, ProviderState.CONNECTING, at=at, reason="connecting")

    def authorized(self, at: datetime) -> None:
        self.status = transition(self.status, ProviderState.SYNCING, at=at, reason="awaiting fresh snapshot")

    def observe(self, message_type: str, at: datetime) -> None:
        self.health.observe(message_type, at)
        if self.status.state == ProviderState.SYNCING and self.health.synchronized:
            self.status = transition(self.status, ProviderState.LIVE, at=at, reason="fresh synchronized feed")

    def freshness_check(self, at: datetime, *, max_age_seconds: float = 5) -> None:
        if self.status.state == ProviderState.LIVE and self.health.stale(at, max_age_seconds=max_age_seconds):
            self.status = transition(self.status, ProviderState.STALE, at=at, reason="feed freshness breached")

    @property
    def authorization_allowed(self) -> bool:
        return self.status.state == ProviderState.LIVE and self.health.synchronized
