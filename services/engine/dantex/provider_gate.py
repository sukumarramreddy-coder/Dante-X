from __future__ import annotations

from dataclasses import dataclass

from .providers.provider_state import ProviderState


@dataclass(frozen=True)
class ProviderGate:
    allowed: bool
    reason: str


def provider_gate(*, state: ProviderState, synchronized: bool, instrument_fresh: bool) -> ProviderGate:
    if state != ProviderState.LIVE:
        return ProviderGate(False, f"provider state is {state.value}")
    if not synchronized:
        return ProviderGate(False, "provider snapshot not synchronized")
    if not instrument_fresh:
        return ProviderGate(False, "instrument tick is stale")
    return ProviderGate(True, "live synchronized fresh provider")
