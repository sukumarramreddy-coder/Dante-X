from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .credentials import UpstoxCredentials
from .upstox import UpstoxConfig
from .upstox_master import instrument_master
from .upstox_rest import UpstoxRestClient


UNDERLYINGS = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
}


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _leg(row: dict[str, Any], side: str) -> dict[str, Any]:
    data = row.get(f"{side}_options") or {}
    market = data.get("market_data") or {}
    greeks = data.get("option_greeks") or {}
    return {
        "instrument_key": data.get("instrument_key"),
        "ltp": _num(market.get("ltp")),
        "volume": market.get("volume"),
        "oi": market.get("oi"),
        "prev_oi": market.get("prev_oi"),
        "bid_price": _num(market.get("bid_price")),
        "bid_qty": market.get("bid_qty"),
        "ask_price": _num(market.get("ask_price")),
        "ask_qty": market.get("ask_qty"),
        "iv": _num(greeks.get("iv")),
        "delta": _num(greeks.get("delta")),
        "gamma": _num(greeks.get("gamma")),
        "theta": _num(greeks.get("theta")),
        "vega": _num(greeks.get("vega")),
    }


@dataclass
class OptionsIntelligence:
    def snapshot(self, symbol: str, *, wings: int = 2) -> dict[str, Any]:
        symbol = symbol.upper()
        underlying_key = UNDERLYINGS[symbol]
        master = instrument_master.index_derivatives(symbol)
        expiries = master.get("expiries") or []
        if not expiries:
            instrument_master.refresh_async()
            return {"symbol": symbol, "status": "MASTER_LOADING", "mode": "shadow"}

        expiry = expiries[0]
        credentials = UpstoxCredentials.from_env()
        client = UpstoxRestClient(UpstoxConfig(access_token=credentials.analytics_token))
        payload = client.option_chain(underlying_key, expiry_date=expiry)
        rows = payload.get("data") or []
        if not rows:
            return {
                "symbol": symbol, "expiry": expiry, "status": "NO_CHAIN_DATA", "mode": "shadow"
            }

        spot = _num(rows[0].get("underlying_spot_price"))
        parsed = []
        for row in rows:
            strike = _num(row.get("strike_price"))
            if strike is None:
                continue
            parsed.append({
                "strike": strike,
                "pcr": _num(row.get("pcr")),
                "call": _leg(row, "call"),
                "put": _leg(row, "put"),
            })
        if not parsed or spot is None:
            return {
                "symbol": symbol, "expiry": expiry, "status": "INCOMPLETE_CHAIN", "mode": "shadow"
            }

        atm = min(parsed, key=lambda x: abs(x["strike"] - spot))["strike"]
        ordered = sorted(parsed, key=lambda x: x["strike"])
        atm_index = next(i for i, x in enumerate(ordered) if x["strike"] == atm)
        selected = ordered[max(0, atm_index - wings): atm_index + wings + 1]
        return {
            "symbol": symbol,
            "underlying_key": underlying_key,
            "spot": spot,
            "expiry": expiry,
            "atm_strike": atm,
            "strikes": selected,
            "status": "OK",
            "mode": "shadow",
        }


options_intelligence = OptionsIntelligence()
