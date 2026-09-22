from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock, Thread
from time import sleep
from zoneinfo import ZoneInfo

from .providers.options_intelligence import options_intelligence
from .providers.upstox_master import instrument_master
from .freshness import market_session
from .validation_recorder import validation_recorder
from .outcome_tracker import OutcomeTracker

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
    last_persisted_at: datetime | None = None
    _started: bool = field(default=False, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    _outcomes: OutcomeTracker = field(default_factory=lambda: OutcomeTracker(validation_recorder), repr=False)

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
                snapshots = {}
                for symbol in ("NIFTY", "BANKNIFTY"):
                    snap = options_intelligence.snapshot(symbol)
                    if snap.get("status") != "OK":
                        raise RuntimeError(f"{symbol}:{snap.get('status')}")
                    snapshots[symbol] = snap
                self._outcomes.observe(snapshots)
                # Persist every successful observation, not only /v1/duel calls.
                # This makes the deployed shadow observer useful unattended:
                # market snapshots continue flowing to the configured durable
                # validation sink while the market is open.
                validation_recorder.record_duel(
                    {
                        "state": "OBSERVATION",
                        "family_counts": {},
                        "readiness": {
                            "observer": True,
                            "nifty": snapshots["NIFTY"].get("status") == "OK",
                            "banknifty": snapshots["BANKNIFTY"].get("status") == "OK",
                        },
                    },
                    {
                        "status": "MARKET_OBSERVATION",
                        "authorization": "NONE",
                    },
                    {
                        "nifty_spot": snapshots["NIFTY"].get("spot"),
                        "banknifty_spot": snapshots["BANKNIFTY"].get("spot"),
                        "nifty_expiry": snapshots["NIFTY"].get("expiry"),
                        "banknifty_expiry": snapshots["BANKNIFTY"].get("expiry"),
                        "nifty_path": snapshots["NIFTY"].get("path_response"),
                        "banknifty_path": snapshots["BANKNIFTY"].get("path_response"),
                    },
                )
                persisted_at = datetime.now(IST)
                with self._lock:
                    self.samples += 1
                    self.last_sample_at = persisted_at
                    self.last_persisted_at = persisted_at
                    self.last_error = None
                    self.state = "SAMPLING"
            except Exception as exc:
                with self._lock:
                    self.last_error = f"{type(exc).__name__}: {str(exc)[:180]}"
                    self.state = "DEGRADED"
            sleep(self.interval_seconds)

    def snapshot(self) -> dict:
        with self._lock:
            now = datetime.now(IST)
            age = (now - self.last_persisted_at).total_seconds() if self.last_persisted_at else None
            freshness = "UNKNOWN" if age is None else ("LIVE" if age < 60 else ("STALE" if age <= 180 else "DEAD"))
            return {
                "state": self.state,
                "freshness": freshness,
                "age_seconds": round(age, 1) if age is not None else None,
                "live_authorization_eligible": freshness == "LIVE",
                "interval_seconds": self.interval_seconds,
                "samples": self.samples,
                "last_sample_at": self.last_sample_at.isoformat() if self.last_sample_at else None,
                "last_persisted_at": self.last_persisted_at.isoformat() if self.last_persisted_at else None,
                "last_error": self.last_error,
                "market_hours": "09:15-15:30 Asia/Kolkata weekdays",
                "mode": "shadow",
            }


observation_loop = ObservationLoop()
