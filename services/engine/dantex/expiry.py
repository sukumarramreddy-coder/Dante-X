from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExpiryRisk:
    minutes_remaining: int
    gamma_risk: float
    theta_risk: float
    authorization_multiplier: float
    label: str


def assess_expiry_risk(
    *,
    now: datetime,
    expiry: datetime,
    gamma: float,
    theta: float,
) -> ExpiryRisk:
    minutes = max(0, int((expiry - now).total_seconds() // 60))
    if minutes <= 90:
        label, multiplier = "extreme", 0.55
    elif minutes <= 360:
        label, multiplier = "high", 0.70
    elif minutes <= 1440:
        label, multiplier = "elevated", 0.85
    else:
        label, multiplier = "normal", 1.0
    gamma_risk = min(100.0, abs(gamma) * (2000 if minutes <= 360 else 1000))
    theta_risk = min(100.0, abs(theta) * (2 if minutes <= 360 else 1))
    return ExpiryRisk(minutes, round(gamma_risk, 1), round(theta_risk, 1), multiplier, label)
