from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock, Thread
from typing import Any

from .credentials import UpstoxCredentials

CORE_KEYS = ("NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank")


def _feeds(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        feeds = message.get("feeds")
        if isinstance(feeds, dict):
            return feeds
    return {}


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
class InstrumentHeartbeat:
    ltp: float | None = None
    exchange_timestamp_ms: int | None = None
    received_at: datetime | None = None
    messages: int = 0


@dataclass
class CoreLiveFeed:
    instrument_keys: tuple[str, ...] = CORE_KEYS
    state: str = "OFFLINE"
    connected: bool = False
    message_count: int = 0
    error: str | None = None
    instruments: dict[str, InstrumentHeartbeat] = field(default_factory=dict)
    _started: bool = field(default=False, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def __post_init__(self) -> None:
        self.instruments = {key: InstrumentHeartbeat() for key in self.instrument_keys}

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self.state = "CONNECTING"
        Thread(target=self._run, name="upstox-core-feed", daemon=True).start()

    def _run(self) -> None:
        try:
            import upstox_client
            credentials = UpstoxCredentials.from_env()
            configuration = upstox_client.Configuration()
            configuration.access_token = credentials.analytics_token
            streamer = upstox_client.MarketDataStreamerV3(
                upstox_client.ApiClient(configuration), list(self.instrument_keys), "full"
            )

            def on_open() -> None:
                with self._lock:
                    self.connected = True
                    self.state = "SYNCING"
                    self.error = None

            def on_message(message: Any) -> None:
                now = datetime.now(timezone.utc)
                feeds = _feeds(message)
                with self._lock:
                    self.message_count += 1
                    for key, payload in feeds.items():
                        if key not in self.instruments:
                            continue
                        beat = self.instruments[key]
                        beat.messages += 1
                        beat.received_at = now
                        ltpc = _find_ltpc(payload)
                        if ltpc is None:
                            continue
                        try:
                            beat.ltp = float(ltpc["ltp"])
                        except (TypeError, ValueError, KeyError):
                            pass
                        try:
                            raw = ltpc.get("ltt")
                            beat.exchange_timestamp_ms = int(raw) if raw is not None else None
                        except (TypeError, ValueError):
                            beat.exchange_timestamp_ms = None
                    if all(x.ltp is not None for x in self.instruments.values()):
                        self.state = "LIVE"

            def on_error(error: Any) -> None:
                with self._lock:
                    self.error = str(error)[:240]
                    self.state = "STALE"

            def on_close(*_args: Any) -> None:
                with self._lock:
                    self.connected = False
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
            rows: dict[str, Any] = {}
            fresh = True
            for key, beat in self.instruments.items():
                age = max(0, int((now - beat.received_at).total_seconds() * 1000)) if beat.received_at else None
                if age is None or age > 15_000:
                    fresh = False
                rows[key] = {
                    "ltp": beat.ltp,
                    "exchange_timestamp_ms": beat.exchange_timestamp_ms,
                    "received_at": beat.received_at.isoformat() if beat.received_at else None,
                    "feed_age_ms": age,
                    "messages": beat.messages,
                }
            state = self.state
            if state == "LIVE" and not fresh:
                state = "STALE"
            return {
                "provider": "upstox",
                "state": state,
                "connected": self.connected,
                "message_count": self.message_count,
                "instruments": rows,
                "mode": "shadow",
                "error": self.error,
            }


core_live_feed = CoreLiveFeed()
