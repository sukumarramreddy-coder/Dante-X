from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceAlert:
    symbol: str
    side: str
    previous_score: float
    current_score: float
    delta: float
    reasons: tuple[str, ...]
    severity: str


def evidence_alert(
    *,
    symbol: str,
    side: str,
    previous_score: float,
    current_score: float,
    reasons: list[str] | tuple[str, ...],
    minimum_change: float = 10.0,
) -> EvidenceAlert | None:
    """Emit an alert only for a meaningful evidence change, not a price tick."""
    delta = current_score - previous_score
    if abs(delta) < minimum_change:
        return None
    magnitude = abs(delta)
    severity = "HIGH" if magnitude >= 25 else "MEDIUM" if magnitude >= 15 else "LOW"
    return EvidenceAlert(
        symbol=symbol,
        side=side,
        previous_score=round(previous_score, 1),
        current_score=round(current_score, 1),
        delta=round(delta, 1),
        reasons=tuple(reasons),
        severity=severity,
    )
