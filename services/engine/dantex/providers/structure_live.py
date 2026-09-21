from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .credentials import UpstoxCredentials
from .upstox import UpstoxConfig
from .upstox_rest import UpstoxRestClient

IST = ZoneInfo("Asia/Kolkata")
KEYS = {"NIFTY": "NSE_INDEX|Nifty 50", "BANKNIFTY": "NSE_INDEX|Nifty Bank"}


def _candles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (payload.get("data") or {}).get("candles") or []
    out = []
    for r in rows:
        if len(r) < 6:
            continue
        out.append({"ts": r[0], "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
                    "close": float(r[4]), "volume": float(r[5]), "oi": float(r[6]) if len(r) > 6 else None})
    return sorted(out, key=lambda x: x["ts"])


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    a = 2 / (period + 1)
    v = sum(values[:period]) / period
    for x in values[period:]:
        v = a * x + (1 - a) * v
    return v


def _atr(rows: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(rows) < period + 1:
        return None
    tr = []
    for prev, cur in zip(rows[-period-1:-1], rows[-period:]):
        tr.append(max(cur["high"]-cur["low"], abs(cur["high"]-prev["close"]), abs(cur["low"]-prev["close"])))
    return round(sum(tr) / period, 2)


def _vwap(rows: list[dict[str, Any]]) -> tuple[float | None, str]:
    # NSE index candles commonly have no meaningful traded volume. Never fake
    # VWAP from zero-volume index bars; expose that limitation explicitly.
    denom = sum(x["volume"] for x in rows)
    if denom <= 0:
        return None, "UNAVAILABLE_NO_INDEX_VOLUME"
    value = sum(((x["high"]+x["low"]+x["close"])/3) * x["volume"] for x in rows) / denom
    return round(value, 2), "OK"


def _prior_day(client: UpstoxRestClient, key: str, today: str) -> dict[str, float] | None:
    payload = client.historical_candles(key, unit="days", interval=1, to_date=today, from_date=today)
    rows = _candles(payload)
    if not rows:
        return None
    # Historical endpoint ordering varies; exclude today's date if present.
    candidates = [x for x in rows if str(x["ts"])[:10] < today]
    row = candidates[-1] if candidates else None
    if row is None:
        return None
    return {"high": row["high"], "low": row["low"], "close": row["close"]}


def structure_snapshot(symbol: str) -> dict[str, Any]:
    symbol = symbol.upper()
    key = KEYS[symbol]
    client = UpstoxRestClient(UpstoxConfig(access_token=UpstoxCredentials.from_env().analytics_token))
    rows = _candles(client.intraday_candles(key, unit="minutes", interval=1))
    now = datetime.now(IST)
    source = "INTRADAY"
    # Around midnight the provider's intraday endpoint can legitimately be empty
    # for the new calendar date. Recover the most recent completed trading
    # session for descriptive context, but mark it ineligible for live voting.
    if not rows:
        from datetime import timedelta
        for days_back in range(1, 8):
            d = (now.date() - timedelta(days=days_back)).isoformat()
            try:
                candidate = _candles(client.historical_candles(
                    key, unit="minutes", interval=1, to_date=d, from_date=d
                ))
            except Exception:
                candidate = []
            if candidate:
                rows = candidate
                source = "HISTORICAL_FALLBACK"
                break
    if not rows:
        return {"symbol": symbol, "status": "NO_INTRADAY_DATA",
                "evidence_eligible": False, "freshness":"UNAVAILABLE", "mode":"shadow"}

    session_date = str(rows[-1]["ts"])[:10]
    today = now.date().isoformat()
    evidence_eligible = source == "INTRADAY" and session_date == today
    freshness = "CURRENT_SESSION" if evidence_eligible else "HISTORICAL_SESSION"

    closes = [x["close"] for x in rows]
    last = rows[-1]
    e9, e20, e50 = _ema(closes, 9), _ema(closes, 20), _ema(closes, 50)
    session_vwap, vwap_status = _vwap(rows)
    opening = rows[:15]
    or_high = max((x["high"] for x in opening), default=None)
    or_low = min((x["low"] for x in opening), default=None)
    trend = "MIXED"
    if e9 is not None and e20 is not None and last["close"] > e9 > e20:
        trend = "BULLISH"
    elif e9 is not None and e20 is not None and last["close"] < e9 < e20:
        trend = "BEARISH"

    breakout = "INSIDE"
    if or_high is not None and last["close"] > or_high:
        breakout = "ABOVE_OPENING_RANGE"
    elif or_low is not None and last["close"] < or_low:
        breakout = "BELOW_OPENING_RANGE"

    prior = None
    try:
        # Fetch a small historical window so previous trading day is available.
        from datetime import timedelta
        prior_payload = client.historical_candles(
            key, unit="days", interval=1,
            to_date=now.date().isoformat(),
            from_date=(now.date()-timedelta(days=7)).isoformat(),
        )
        daily = _candles(prior_payload)
        candidates = [x for x in daily if str(x["ts"])[:10] < now.date().isoformat()]
        if candidates:
            p = candidates[-1]
            prior = {"high": p["high"], "low": p["low"], "close": p["close"]}
    except Exception:
        prior = None

    location = {
        "vs_vwap": None if session_vwap is None else ("ABOVE" if last["close"] > session_vwap else "BELOW" if last["close"] < session_vwap else "AT"),
        "vs_prior_high": None if not prior else ("ABOVE" if last["close"] > prior["high"] else "BELOW"),
        "vs_prior_low": None if not prior else ("ABOVE" if last["close"] > prior["low"] else "BELOW"),
    }
    return {
        "symbol": symbol, "instrument_key": key, "last": last["close"], "last_candle_ts": last["ts"],
        "data_source": source, "session_date": session_date, "freshness": freshness,
        "evidence_eligible": evidence_eligible,
        "recent_candles": rows[-60:],
        "candles": len(rows), "vwap": session_vwap, "vwap_status": vwap_status, "ema9": round(e9,2) if e9 else None,
        "ema20": round(e20,2) if e20 else None, "ema50": round(e50,2) if e50 else None,
        "atr14": _atr(rows), "opening_range": {"high": or_high, "low": or_low},
        "prior_day": prior, "trend": trend, "opening_range_state": breakout,
        "location": location, "status": "OK", "mode": "shadow",
    }
