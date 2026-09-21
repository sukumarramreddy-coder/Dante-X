from __future__ import annotations
from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Any

IST = ZoneInfo("Asia/Kolkata")
OPEN = time(9,15)
CLOSE = time(15,30)

def market_session(now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(IST)).astimezone(IST)
    weekday = now.weekday() < 5
    active = weekday and OPEN <= now.time() <= CLOSE
    return {"now":now.isoformat(),"session_date":now.date().isoformat(),
            "market_open":active,"timezone":"Asia/Kolkata"}

def gate(*, source: str, timestamp: str | None = None,
         session_date: str | None = None, provider_fresh: bool | None = None,
         require_open: bool = True, now: datetime | None = None) -> dict[str, Any]:
    """Single fail-closed freshness decision for live evidence."""
    session=market_session(now)
    reasons=[]
    if require_open and not session["market_open"]:
        reasons.append("market session is closed")
    if session_date and session_date != session["session_date"]:
        reasons.append(f"source session {session_date} != active session {session['session_date']}")
    if provider_fresh is False:
        reasons.append("provider marked snapshot stale")
    if timestamp:
        try:
            ts=datetime.fromisoformat(timestamp.replace("Z","+00:00")).astimezone(IST)
            age=max(0.0,((now or datetime.now(IST)).astimezone(IST)-ts).total_seconds())
            if session["market_open"] and age > 180:
                reasons.append(f"snapshot age {age:.0f}s exceeds live tolerance")
        except ValueError:
            reasons.append("unparseable source timestamp")
    elif session["market_open"] and provider_fresh is not True:
        reasons.append("live timestamp/freshness not proven")
    eligible=not reasons
    return {"source":source,"eligible":eligible,
            "state":"LIVE" if eligible else "STALE_CONTEXT",
            "session":session,"reasons":reasons}
