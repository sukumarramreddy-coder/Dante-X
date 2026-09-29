from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone, timedelta
from threading import Lock, Thread
from urllib.request import Request, urlopen

from .instruments import Instrument, build_universe

NSE_MASTER_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"


@dataclass
class InstrumentMaster:
    loaded_at: datetime | None = None
    instruments: tuple[Instrument, ...] = ()
    error: str | None = None
    _loading: bool = field(default=False, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def refresh_async(self, *, max_age_hours: int = 12) -> None:
        with self._lock:
            if self._loading:
                return
            if self.loaded_at and datetime.now(timezone.utc) - self.loaded_at < timedelta(hours=max_age_hours):
                return
            self._loading = True
        Thread(target=self._refresh, name="upstox-instrument-master", daemon=True).start()

    def _refresh(self) -> None:
        try:
            request = Request(NSE_MASTER_URL, headers={"User-Agent": "Dante-X/0.1"})
            with urlopen(request, timeout=30) as response:
                rows = json.loads(gzip.decompress(response.read()))
            universe = build_universe(rows)
            with self._lock:
                self.instruments = universe
                self.loaded_at = datetime.now(timezone.utc)
                self.error = None
        except Exception as exc:
            with self._lock:
                self.error = type(exc).__name__
        finally:
            with self._lock:
                self._loading = False

    def index_derivatives(self, name: str, *, today: date | None = None) -> dict:
        today = today or date.today()
        needle = name.upper()
        with self._lock:
            matches = [
                x for x in self.instruments
                if needle in (x.name + " " + x.trading_symbol).upper()
                and x.expiry is not None and x.expiry >= today
                and x.instrument_type in {"CE", "PE", "FUT", "FUTIDX"}
            ]
            expiries = sorted({x.expiry.isoformat() for x in matches if x.expiry})
            return {
                "query": name,
                "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
                "contracts": len(matches),
                "expiries": expiries[:8],
                "error": self.error,
            }


instrument_master = InstrumentMaster()
