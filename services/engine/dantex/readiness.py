from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Readiness:
    ready: bool
    mode: str
    blockers: tuple[str, ...]


def production_readiness(
    *,
    live_provider_connected: bool,
    historical_validation_complete: bool,
    calibration_publishable: bool,
    ci_green: bool,
) -> Readiness:
    blockers = []
    if not live_provider_connected:
        blockers.append("live provider not connected")
    if not historical_validation_complete:
        blockers.append("historical validation incomplete")
    if not calibration_publishable:
        blockers.append("probability calibration not publishable")
    if not ci_green:
        blockers.append("CI not green")
    return Readiness(not blockers, "live" if not blockers else "shadow", tuple(blockers))
