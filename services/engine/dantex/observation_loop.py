from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock, Thread
from time import sleep
from zoneinfo import ZoneInfo

from .providers.options_intelligence import options_intelligence
from .providers.upstox_master import instrument_master
from .freshness import market_session

IST = ZoneInfo("Asia/Kolkata")


def _market_window(now: datetime) -> bool:
    return bool(market_session(now).get("market_open"))


@dataclass
class ObservationLoop:
    interval_seconds: int = 30
    state: str = "OFFLINE"
    samples: int = 0
    last_sample_at: datetime | None = None
    last_error: str | None = None
    _started: bool = field(default=False, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self.state = "STARTING"
        Thread(target=self._run, name="dantex-observation-loop", daemon=True).start()

    def _run(self) -> None:
        while True:
            now = datetime.now(IST)
            if not _market_window(now):
                with self._lock:
                    self.state = "MARKET_CLOSED"
                sleep(60)
                continue
            try:
                instrument_master.refresh_async()
                # Snapshot both underlyings on the same cadence. The option
                # intelligence object owns bounded per-symbol history.
                for symbol in ("NIFTY", "BANKNIFTY"):
                    snap = options_intelligence.snapshot(symbol)
                    if snap.get("status") != "OK":
                        raise RuntimeError(f"{symbol}:{snap.get('status')}")
                with self._lock:
                    self.samples += 1
                    self.last_sample_at = datetime.now(IST)
                    self.last_error = None
                    self.state = "SAMPLING"
            except Exception as exc:
                with self._lock:
                    self.last_error = f"{type(exc).__name__}: {str(exc)[:180]}"
                    self.state = "DEGRADED"
            sleep(self.interval_seconds)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "state": self.state,
                "interval_seconds": self.interval_seconds,
                "samples": self.samples,
                "last_sample_at": self.last_sample_at.isoformat() if self.last_sample_at else None,
                "last_error": self.last_error,
                "market_hours": "09:15-15:30 Asia/Kolkata weekdays",
                "mode": "shadow",
            }


observation_loop = ObservationLoop()
