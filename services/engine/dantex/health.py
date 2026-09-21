from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .providers.provider_state import ProviderState


@dataclass(frozen=True)
class HealthSnapshot:
    service: str
    mode: str
    provider: str
    provider_state: str
    signal_authorization: bool
    timestamp: str


def snapshot(*, mode: str, provider_state: ProviderState, authorization_allowed: bool, now: datetime) -> HealthSnapshot:
    return HealthSnapshot(
        service="dante-x-engine",
        mode=mode,
        provider="upstox",
        provider_state=provider_state.value,
        signal_authorization=authorization_allowed and mode == "live",
        timestamp=now.isoformat(),
    )
