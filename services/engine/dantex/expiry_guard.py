from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpiryGuard:
    allowed: bool
    required_confirmation: float
    required_potential: float
    reason: str


def expiry_guard(*, minutes_to_expiry: int) -> ExpiryGuard:
    if minutes_to_expiry <= 30:
        return ExpiryGuard(False, 90, 90, "new directional option entries blocked in final 30 minutes")
    if minutes_to_expiry <= 120:
        return ExpiryGuard(True, 80, 80, "extreme gamma/theta window")
    if minutes_to_expiry <= 360:
        return ExpiryGuard(True, 72, 70, "elevated expiry risk")
    return ExpiryGuard(True, 60, 55, "normal expiry authorization")
