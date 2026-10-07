from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PositioningSnapshot:
    pcr_oi: float | None
    call_wall: float | None
    put_wall: float | None
    call_oi_change: float
    put_oi_change: float
    state: str
    counterweights: tuple[str, ...]


def positioning_snapshot(rows: list[dict[str, Any]], *, spot: float | None = None) -> PositioningSnapshot:
    """Describe OI/PCR and walls once; never multiply them into independent votes."""
    usable = [r for r in rows if r.get("strike") is not None]
    call_oi = sum(float((r.get("call") or {}).get("oi") or 0) for r in usable)
    put_oi = sum(float((r.get("put") or {}).get("oi") or 0) for r in usable)
    call_doi = sum(float((r.get("call") or {}).get("oi_change") or 0) for r in usable)
    put_doi = sum(float((r.get("put") or {}).get("oi_change") or 0) for r in usable)
    pcr = put_oi / call_oi if call_oi else None

    call_wall_row = max(usable, key=lambda r: float((r.get("call") or {}).get("oi") or 0), default=None)
    put_wall_row = max(usable, key=lambda r: float((r.get("put") or {}).get("oi") or 0), default=None)
    call_wall = float(call_wall_row["strike"]) if call_wall_row else None
    put_wall = float(put_wall_row["strike"]) if put_wall_row else None

    if pcr is not None and pcr >= 1.15 and put_doi > call_doi:
        state = "PUT_SUPPORT_DOMINANT"
    elif pcr is not None and pcr <= 0.85 and call_doi > put_doi:
        state = "CALL_RESISTANCE_DOMINANT"
    else:
        state = "BALANCED"

    counterweights: list[str] = []
    if spot is not None and call_wall is not None and call_wall >= spot:
        counterweights.append(f"call OI wall {call_wall:g} overhead")
    if spot is not None and put_wall is not None and put_wall <= spot:
        counterweights.append(f"put OI wall {put_wall:g} below")

    return PositioningSnapshot(
        pcr_oi=round(pcr, 3) if pcr is not None else None,
        call_wall=call_wall,
        put_wall=put_wall,
        call_oi_change=round(call_doi, 1),
        put_oi_change=round(put_doi, 1),
        state=state,
        counterweights=tuple(counterweights),
    )
