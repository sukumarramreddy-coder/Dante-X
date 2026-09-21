from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock, Thread
from typing import Any

from .credentials import UpstoxCredentials

NIFTY_KEY = "NSE_INDEX|Nifty 50"


def _find_ltpc(node: Any) -> dict[str, Any] | None:
    if isinstance(node, dict):
        value = node.get("ltpc")
        if isinstance(value, dict) and "ltp" in value:
            return value
        for child in node.values():
            found = _find_ltpc(child)
            if found is not None:
                return found
    elif isinstance(node, list):
        for child in node:
            found = _find_ltpc(child)
            if found is not None:
                return found
    return None


@dataclass
class NiftyLiveProbe:
    instrument_key: str = NIFTY_KEY
    state: str = "OFFLINE"
    connected: bool = False
    message_count: int = 0
    ltp: float | None = None
    exchange_timestamp_ms: int | None = None
    received_at: datetime | None = None
    error: str | None = None
    _started: bool = field(default=False, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self.state = "CONNECTING"
        Thread(target=self._run, name="upstox-nifty-feed", daemon=True).start()

    def _run(self) -> None:
        try:
            import upstox_client

            credentials = UpstoxCredentials.from_env()
            configuration = upstox_client.Configuration()
            configuration.access_token = credentials.analytics_token
            streamer = upstox_client.MarketDataStreamerV3(
                upstox_client.ApiClient(configuration), [self.instrument_key], "ltpc"
            )

            def on_open() -> None:
                with self._lock:
                    self.connected = True
                    self.state = "SYNCING"
                    self.error = None

            def on_message(message: Any) -> None:
                now = datetime.now(timezone.utc)
                ltpc = _find_ltpc(message)
                with self._lock:
                    self.message_count += 1
                    self.received_at = now
                    if ltpc is not None:
                        try:
                            self.ltp = float(ltpc["ltp"])
                        except (TypeError, ValueError, KeyError):
                            pass
                        raw_ltt = ltpc.get("ltt")
                        try:
                            self.exchange_timestamp_ms = int(raw_ltt) if raw_ltt is not None else None
                        except (TypeError, ValueError):
                            self.exchange_timestamp_ms = None
                        if self.ltp is not None:
                            self.state = "LIVE"

            def on_error(error: Any) -> None:
                with self._lock:
                    self.error = str(error)[:240]
                    self.state = "STALE"

            def on_close(*_args: Any) -> None:
                with self._lock:
                    self.connected = False
                    if self.state != "OFFLINE":
                        self.state = "STALE"

            streamer.on("open", on_open)
            streamer.on("message", on_message)
            streamer.on("error", on_error)
            streamer.on("close", on_close)
            streamer.auto_reconnect(True, 5, 10)
            streamer.connect()
        except Exception as exc:
            with self._lock:
                self.error = f"{type(exc).__name__}: {str(exc)[:180]}"
                self.state = "OFFLINE"
                self.connected = False

    def snapshot(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with self._lock:
            received = self.received_at
            age_ms = max(0, int((now - received).total_seconds() * 1000)) if received else None
            state = self.state
            if state == "LIVE" and age_ms is not None and age_ms > 15_000:
                state = "STALE"
            return {
                "provider": "upstox",
                "instrument": self.instrument_key,
                "state": state,
                "connected": self.connected,
                "message_count": self.message_count,
                "ltp": self.ltp,
                "exchange_timestamp_ms": self.exchange_timestamp_ms,
                "received_at": received.isoformat() if received else None,
                "feed_age_ms": age_ms,
                "mode": "shadow",
                "error": self.error,
            }


nifty_live_probe = NiftyLiveProbe()
