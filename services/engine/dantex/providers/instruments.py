from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Instrument:
    instrument_key: str
    trading_symbol: str
    name: str
    segment: str
    exchange: str
    instrument_type: str
    expiry: date | None = None
    strike: float | None = None
    lot_size: int | None = None


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    # Upstox instrument masters can encode expiry as epoch milliseconds.
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc).date()
    text = str(value).strip()
    if text.isdigit():
        return datetime.fromtimestamp(int(text) / 1000, tz=timezone.utc).date()
    return date.fromisoformat(text[:10])


def normalize_instrument(row: dict[str, Any]) -> Instrument:
    key = row.get("instrument_key")
    if not key:
        raise ValueError("instrument_key is required")
    return Instrument(
        instrument_key=str(key),
        trading_symbol=str(row.get("trading_symbol") or ""),
        name=str(row.get("name") or ""),
        segment=str(row.get("segment") or ""),
        exchange=str(row.get("exchange") or ""),
        instrument_type=str(row.get("instrument_type") or ""),
        expiry=_date(row.get("expiry")),
        strike=float(row["strike_price"]) if row.get("strike_price") is not None else None,
        lot_size=int(row["lot_size"]) if row.get("lot_size") is not None else None,
    )


def build_universe(rows: list[dict[str, Any]], *, segments: set[str] | None = None) -> tuple[Instrument, ...]:
    instruments = (normalize_instrument(row) for row in rows)
    if segments is not None:
        instruments = (x for x in instruments if x.segment in segments)
    return tuple(instruments)
