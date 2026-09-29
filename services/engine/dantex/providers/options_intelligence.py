from __future__ import annotations

from math import isfinite
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any
from collections import deque
from threading import Lock
from time import time

from .credentials import UpstoxCredentials
from .upstox import UpstoxConfig
from .upstox_master import instrument_master
from .upstox_rest import UpstoxRestClient
from .verified_option_quotes import verified_prices


UNDERLYINGS = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
}


def _num(value: Any) -> float | None:
    try:
        number = float(value) if value is not None and not isinstance(value, bool) else None
        return number if number is not None and isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _leg(row: dict[str, Any], side: str) -> dict[str, Any]:
    data = row.get(f"{side}_options") or {}
    market = data.get("market_data") or {}
    greeks = data.get("option_greeks") or {}
    ltp = _num(market.get("ltp"))
    bid = _num(market.get("bid_price"))
    ask = _num(market.get("ask_price"))
    oi = _num(market.get("oi"))
    prev_oi = _num(market.get("prev_oi"))
    spread = (ask - bid) if bid is not None and ask is not None else None
    spread_pct = (spread / ltp * 100) if spread is not None and ltp and ltp > 0 else None
    oi_change = (oi - prev_oi) if oi is not None and prev_oi is not None else None
    oi_change_pct = (oi_change / prev_oi * 100) if oi_change is not None and prev_oi else None
    return {
        "instrument_key": data.get("instrument_key"),
        "ltp": ltp,
        "volume": market.get("volume"),
        "oi": oi,
        "prev_oi": prev_oi,
        "oi_change": oi_change,
        "oi_change_pct": round(oi_change_pct, 2) if oi_change_pct is not None else None,
        "bid_price": bid,
        "bid_qty": market.get("bid_qty"),
        "ask_price": ask,
        "spread": round(spread, 4) if spread is not None else None,
        "spread_pct": round(spread_pct, 3) if spread_pct is not None else None,
        "ask_qty": market.get("ask_qty"),
        "iv": _num(greeks.get("iv")),
        "delta": _num(greeks.get("delta")),
        "gamma": _num(greeks.get("gamma")),
        "theta": _num(greeks.get("theta")),
        "vega": _num(greeks.get("vega")),
    }


def _quality(leg: dict[str, Any]) -> dict[str, Any]:
    spread_pct = leg.get("spread_pct")
    volume = leg.get("volume") or 0
    oi = leg.get("oi") or 0
    # Execution-quality score only; deliberately not a directional signal.
    spread_score = 40 if spread_pct is not None and spread_pct <= 0.5 else 30 if spread_pct is not None and spread_pct <= 1.0 else 15 if spread_pct is not None and spread_pct <= 2.0 else 0
    volume_score = 30 if volume >= 1_000_000 else 20 if volume >= 250_000 else 10 if volume >= 50_000 else 0
    oi_score = 30 if oi >= 250_000 else 20 if oi >= 100_000 else 10 if oi >= 25_000 else 0
    score = spread_score + volume_score + oi_score
    return {
        "execution_score": score,
        "grade": "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D",
    }


def _response_summary(strikes: list[dict[str, Any]], atm: float) -> dict[str, Any]:
    """Descriptive CE/PE positioning evidence; not a directional trade signal."""
    near = [x for x in strikes if abs(x["strike"] - atm) <= 100]
    def agg(side: str) -> dict[str, Any]:
        legs = [x[side] for x in near]
        oi_change = sum((x.get("oi_change") or 0) for x in legs)
        volume = sum((x.get("volume") or 0) for x in legs)
        ivs = [x["iv"] for x in legs if x.get("iv") is not None]
        spreads = [x["spread_pct"] for x in legs if x.get("spread_pct") is not None]
        qualities = [x.get("quality", {}).get("execution_score") for x in legs]
        qualities = [x for x in qualities if x is not None]
        return {
            "near_atm_oi_change": oi_change,
            "near_atm_volume": volume,
            "avg_iv": round(sum(ivs) / len(ivs), 3) if ivs else None,
            "avg_spread_pct": round(sum(spreads) / len(spreads), 3) if spreads else None,
            "avg_execution_score": round(sum(qualities) / len(qualities), 1) if qualities else None,
        }
    call = agg("call")
    put = agg("put")
    return {
        "call": call,
        "put": put,
        "volume_ratio_put_call": round(put["near_atm_volume"] / call["near_atm_volume"], 3) if call["near_atm_volume"] else None,
        "oi_change_ratio_put_call": round(put["near_atm_oi_change"] / call["near_atm_oi_change"], 3) if call["near_atm_oi_change"] else None,
        "classification": "DESCRIPTIVE_ONLY",
        "note": "Positioning/quality snapshot only; direction requires time-series price response and market confirmation.",
    }


@dataclass
class OptionsIntelligence:
    _history: dict[str, deque] = None
    _lock: Lock = None

    def __post_init__(self) -> None:
        self._history = {}
        self._lock = Lock()

    def _track(self, symbol: str, spot: float, atm: float, strikes: list[dict[str, Any]], *, expiry: str | None = None) -> dict[str, Any]:
        now = time()
        local_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        atm_row = min(strikes, key=lambda x: abs(x["strike"] - atm))
        point = {
            "ts": now, "iso_ts": local_now.isoformat(), "session_date": local_now.date().isoformat(), "spot": spot,
            "contract_identity": (expiry, atm_row["strike"],
                                  atm_row["call"].get("instrument_key"),
                                  atm_row["put"].get("instrument_key")),
            "call_ltp": atm_row["call"].get("ltp"),
            "put_ltp": atm_row["put"].get("ltp"),
            "call_iv": atm_row["call"].get("iv"),
            "put_iv": atm_row["put"].get("iv"),
            "call_oi": atm_row["call"].get("oi"),
            "put_oi": atm_row["put"].get("oi"),
        }
        with self._lock:
            history = self._history.setdefault(symbol, deque(maxlen=60))
            # Never compare different contracts or carry yesterday into today.
            if history and (history[-1]["contract_identity"] != point["contract_identity"]
                            or history[-1]["session_date"] != point["session_date"]):
                history.clear()
            history.append(point)
            if len(history) < 2:
                return {"state": "BUILDING_BASELINE", "samples": len(history)}
            base = history[0]
            latest = history[-1]
        def pct(a: Any, b: Any) -> float | None:
            return round((b - a) / a * 100, 3) if a not in (None, 0) and b is not None else None
        spot_change = latest["spot"] - base["spot"]
        call_pct = pct(base["call_ltp"], latest["call_ltp"])
        put_pct = pct(base["put_ltp"], latest["put_ltp"])
        classification = "NO_EDGE"
        if abs(spot_change) >= 5 and call_pct is not None and put_pct is not None:
            if spot_change > 0 and call_pct > 0 and put_pct < 0:
                classification = "CE_STRENGTHENING"
            elif spot_change < 0 and put_pct > 0 and call_pct < 0:
                classification = "PE_STRENGTHENING"
            elif spot_change > 0 and put_pct >= 0:
                classification = "BULL_MOVE_REFUSED_BY_OPTIONS"
            elif spot_change < 0 and call_pct >= 0:
                classification = "BEAR_MOVE_REFUSED_BY_OPTIONS"
            else:
                classification = "CONFLICT"
        return {
            "state": classification,
            "samples": len(history),
            "window_seconds": round(latest["ts"] - base["ts"], 1),
            "spot_change": round(spot_change, 2),
            "atm_call_change_pct": call_pct,
            "atm_put_change_pct": put_pct,
            "last_sample_at": latest.get("iso_ts"),
            "session_date": latest.get("session_date"),
            "note": "Live path evidence only; not trade authorization.",
        }
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
            call = _leg(row, "call")
            put = _leg(row, "put")
            call["quality"] = _quality(call)
            put["quality"] = _quality(put)
            parsed.append({
                "strike": strike,
                "pcr": _num(row.get("pcr")),
                "call": call,
                "put": put,
            })
        if not parsed or spot is None:
            return {
                "symbol": symbol, "expiry": expiry, "status": "INCOMPLETE_CHAIN", "mode": "shadow"
            }

        atm = min(parsed, key=lambda x: abs(x["strike"] - spot))["strike"]
        ordered = sorted(parsed, key=lambda x: x["strike"])
        atm_index = next(i for i, x in enumerate(ordered) if x["strike"] == atm)
        selected = ordered[max(0, atm_index - wings): atm_index + wings + 1]
        eligible = False
        quote_timestamp = None
        try:
            keys = [underlying_key] + [row[side]["instrument_key"] for row in selected for side in ("call", "put")]
            selected, spot, quote_timestamp = verified_prices(selected, underlying_key, client.full_market_quotes(keys))
            for row in selected:
                for side in ("call", "put"):
                    row[side]["quality"] = _quality(row[side])
            eligible = True
        except Exception:
            # A stale path must not become the baseline of a later fresh path.
            with self._lock:
                self._history.pop(symbol, None)
        path = self._track(symbol, spot, atm, selected, expiry=expiry) if eligible else {"state": "STALE_CONTEXT"}
        if eligible:
            path["last_sample_at"] = quote_timestamp
            path["session_date"] = datetime.fromisoformat(quote_timestamp).astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
        return {
            "symbol": symbol,
            "underlying_key": underlying_key,
            "spot": spot,
            "expiry": expiry,
            "atm_strike": atm,
            "strikes": selected,
            "response": _response_summary(selected, atm),
            "path_response": path,
            "quality": {
                "selection": "nearest-expiry ATM +/- 2 strikes",
                "metrics": ["spread_pct", "oi_change", "oi_change_pct", "volume", "greeks", "execution_score"],
                "note": "execution_score measures tradability only, not bullish/bearish direction",
            },
            "status": "OK",
            "evidence_eligible": eligible,
            "derivatives_evidence_eligible": False,
            "freshness_reason": "verified V3 quote prices/depth; chain Greeks remain context" if eligible else "option quote freshness not proven",
            "mode": "shadow",
        }


options_intelligence = OptionsIntelligence()
