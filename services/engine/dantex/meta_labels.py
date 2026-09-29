"""Offline triple-barrier labels from the SAME option contract's observed OHLC."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .challengers import aware
from .probability import finite_number


def triple_barrier(*, contract: str, as_of: datetime, entry: float, stop: float,
                   target: float, bars: list[dict], evaluated_at: datetime) -> dict:
    """Thirty-minute/session cutoff; dual touches and gaps are censored.

    Bars use opening timestamps at one-minute frequency. Entry is a reference,
    never an assumed execution. The decision must be made on a minute boundary.
    """
    if (not contract or not aware(as_of) or not aware(evaluated_at) or evaluated_at < as_of
            or as_of.second or as_of.microsecond
            or not all(finite_number(x) for x in (entry, stop, target))
            or not 0 < stop < entry < target):
        raise ValueError("invalid barrier event")
    local = as_of.astimezone(ZoneInfo("Asia/Kolkata"))
    close = local.replace(hour=15, minute=30, second=0, microsecond=0)
    if local.weekday() >= 5 or not local.replace(hour=9, minute=15) <= local < close:
        raise ValueError("event outside regular session")
    deadline = min(as_of + timedelta(minutes=30), close)
    expected = as_of
    result = {"status": "CENSORED", "outcome": None, "contract": contract,
              "as_of": as_of.isoformat(), "deadline": deadline.isoformat(),
              "event": "T1_BEFORE_STOP_30M_SESSION", "calibration_ready": False,
              "fill_assumed": False, "costs_included": False}
    for bar in bars:
        at = bar.get("at")
        if not aware(at) or at != expected or bar.get("contract") != contract:
            return {**result, "reason": "gap, ordering or contract identity mismatch"}
        end = at + timedelta(minutes=1)
        if end > deadline or end > evaluated_at:
            break
        low, high = bar.get("low"), bar.get("high")
        if not all(finite_number(x) for x in (low, high)) or not 0 < low <= high:
            return {**result, "reason": "invalid observed bar"}
        if low <= stop and high >= target:
            return {**result, "reason": "intrabar order ambiguous"}
        if low <= stop or high >= target:
            hit = high >= target
            return {**result, "status": "TARGET" if hit else "STOP", "outcome": hit,
                    "label_available_at": end.isoformat()}
        expected = end
    if expected == deadline and evaluated_at >= deadline:
        return {**result, "status": "TIMEOUT", "outcome": False,
                "label_available_at": deadline.isoformat()}
    return {**result, "reason": "incomplete future coverage"}
