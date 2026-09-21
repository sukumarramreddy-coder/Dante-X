from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..market import Quote


@dataclass(frozen=True)
class UpstoxConfig:
    access_token: str
    rest_base: str = "https://api.upstox.com"
    api_version: str = "2.0"


class UpstoxNormalizer:
    """Pure normalization layer. Network/auth transport is injected separately."""

    @staticmethod
    def quote(instrument_key: str, feed: dict[str, Any]) -> Quote:
        ltpc = feed.get("ltpc") or feed.get("fullFeed", {}).get("marketFF", {}).get("ltpc", {})
        depth = feed.get("firstDepth", {})
        ltt = ltpc.get("ltt")
        if ltt is None:
            raise ValueError("Upstox tick missing exchange last-traded timestamp")
        ts = datetime.fromtimestamp(int(ltt) / 1000).astimezone()
        return Quote(
            symbol=instrument_key,
            timestamp=ts,
            ltp=float(ltpc["ltp"]),
            bid=float(depth["bidP"]) if depth.get("bidP") is not None else None,
            ask=float(depth["askP"]) if depth.get("askP") is not None else None,
        )

    @staticmethod
    def option_state(instrument_key: str, feed: dict[str, Any]) -> dict[str, Any]:
        first = feed.get("firstLevelWithGreeks", feed)
        ltpc = first.get("ltpc", {})
        depth = first.get("firstDepth", {})
        greeks = first.get("optionGreeks", {})
        return {
            "instrument_key": instrument_key,
            "ltp": ltpc.get("ltp"),
            "bid": depth.get("bidP"),
            "ask": depth.get("askP"),
            "delta": greeks.get("delta"),
            "gamma": greeks.get("gamma"),
            "theta": greeks.get("theta"),
            "vega": greeks.get("vega"),
            "iv": greeks.get("iv"),
            "volume": first.get("vtt"),
            "oi": first.get("oi"),
        }
