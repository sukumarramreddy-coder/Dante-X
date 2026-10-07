from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .outcome_labeler import label_from_path
from .probability import finite_number

IST = ZoneInfo("Asia/Kolkata")


class OutcomeTracker:
    """Forward-only shadow outcomes; never backfill pre-start audit records."""

    def __init__(self, recorder, horizon_minutes: int = 30, *, started_at=None):
        self.recorder = recorder
        self.horizon = timedelta(minutes=horizon_minutes)
        self.started_at = (started_at or datetime.now(IST)).astimezone(IST)
        self.paths: dict[int, list[dict]] = {}

    def observe(self, option_snapshots: dict, *, now=None) -> int:
        now = (now or datetime.now(IST)).astimezone(IST)
        labelled = 0
        # Eligibility is filtered in SQL before LIMIT. Pre-start records remain intact.
        for sample in self.recorder.unlabelled(200, since=self.started_at.isoformat()):
            try:
                started = datetime.fromisoformat(sample["recorded_at"])
                if started.tzinfo is None or started < self.started_at or started > now:
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            started = started.astimezone(IST)
            deadline = min(started + self.horizon,
                           started.replace(hour=15, minute=30, second=0, microsecond=0))
            key = ((sample.get("decision") or {}).get("contract") or {}).get("instrument_key")
            path = self.paths.get(sample["id"], [])
            for snap in option_snapshots.values():
                if snap.get("evidence_eligible") is not True:
                    continue
                for row in snap.get("strikes") or []:
                    for side in ("call", "put"):
                        leg = row.get(side) or {}
                        if not key or leg.get("instrument_key") != key:
                            continue
                        try:
                            at = datetime.fromisoformat(leg["price_timestamp"])
                            if at.tzinfo is None:
                                continue
                        except (KeyError, TypeError, ValueError):
                            continue
                        price = leg.get("ltp")
                        if (finite_number(price) and price > 0 and started < at <= min(now, deadline)
                                and (now-at).total_seconds() <= 60
                                and (not path or at > datetime.fromisoformat(path[-1]["at"]))):
                            path.append({"at": at.isoformat(), "premium": price})
                            self.paths[sample["id"]] = path
            if now < deadline:
                continue
            # A partial or gapped path cannot establish a first-hit outcome.
            stamps = [started] + [datetime.fromisoformat(p["at"]) for p in path] + [deadline]
            complete = bool(path) and all(0 <= (b-a).total_seconds() <= 90
                                         for a, b in zip(stamps, stamps[1:]))
            outcome = label_from_path(sample, path) if complete else None
            if outcome is None:
                outcome = {"eligible": False, "status": "CENSORED",
                           "reason": "missing or incomplete forward price observations",
                           "observations": len(path), "deadline": deadline.isoformat()}
            self.recorder.label(sample["id"], outcome)
            self.paths.pop(sample["id"], None)
            labelled += 1
        return labelled
