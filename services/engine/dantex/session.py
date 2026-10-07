from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from .domain import Horizon


IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class SessionPolicy:
    horizon: Horizon
    entry_cutoff: time
    force_exit: time | None


INTRADAY_POLICY = SessionPolicy(Horizon.INTRADAY, time(15, 10), time(15, 20))


def intraday_session_status(now: datetime, policy: SessionPolicy = INTRADAY_POLICY) -> str:
    local = now.astimezone(IST)
    clock = local.time().replace(tzinfo=None)
    if local.weekday() >= 5:
        return "closed"
    if clock < time(9, 15):
        return "preopen"
    if clock >= (policy.force_exit or time(23, 59)):
        return "force_exit"
    if clock >= policy.entry_cutoff:
        return "manage_only"
    return "entry_allowed"
