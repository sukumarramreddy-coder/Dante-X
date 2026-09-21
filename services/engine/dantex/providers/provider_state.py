from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ProviderState(StrEnum):
    OFFLINE = "offline"
    CONNECTING = "connecting"
    SYNCING = "syncing"
    LIVE = "live"
    STALE = "stale"
    RECONNECTING = "reconnecting"


@dataclass(frozen=True)
class ProviderStatus:
    state: ProviderState
    changed_at: datetime
    reason: str


_ALLOWED = {
    ProviderState.OFFLINE: {ProviderState.CONNECTING},
    ProviderState.CONNECTING: {ProviderState.SYNCING, ProviderState.OFFLINE},
    ProviderState.SYNCING: {ProviderState.LIVE, ProviderState.RECONNECTING, ProviderState.OFFLINE},
    ProviderState.LIVE: {ProviderState.STALE, ProviderState.RECONNECTING, ProviderState.OFFLINE},
    ProviderState.STALE: {ProviderState.RECONNECTING, ProviderState.OFFLINE},
    ProviderState.RECONNECTING: {ProviderState.SYNCING, ProviderState.OFFLINE},
}


def transition(current: ProviderStatus, target: ProviderState, *, at: datetime, reason: str) -> ProviderStatus:
    if target not in _ALLOWED[current.state]:
        raise ValueError(f"invalid provider transition {current.state} -> {target}")
    return ProviderStatus(target, at, reason)
