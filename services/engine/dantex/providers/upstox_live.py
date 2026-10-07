from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock, Thread
from typing import Any

from .credentials import UpstoxCredentials
from .tick_integrity import valid_tick, tick_fresh

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
                feeds = message.get("feeds", {}) if isinstance(message, dict) else {}
                ltpc = _find_ltpc(feeds.get(self.instrument_key)) if isinstance(feeds, dict) else None
                with self._lock:
                    self.message_count += 1
                    tick = valid_tick(ltpc, now)
                    if tick is None:
                        self.state = "STALE"
                        return
                    self.ltp, self.exchange_timestamp_ms = tick
                    self.received_at = now
                    self.state = "LIVE"

            def on_error(error: Any) -> None:
                with self._lock:
                    self.error = "provider stream error"
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
                self.error = type(exc).__name__
                self.state = "OFFLINE"
                self.connected = False

    def snapshot(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with self._lock:
            received = self.received_at
            age_ms = max(0, int((now - received).total_seconds() * 1000)) if received else None
            state = self.state
            if state == "LIVE" and (not self.connected or not tick_fresh(self.ltp, self.exchange_timestamp_ms, received, now)):
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
