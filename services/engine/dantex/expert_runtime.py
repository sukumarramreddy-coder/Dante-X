"""Reuse the observer and validation recorder; no second service or broker interface."""
from copy import deepcopy
from threading import Lock

from .expert_engine import four_way, reconcile
from .expert_provider import OpenAIExpertReasoningProvider, snapshot_digest
from .expert_snapshot import normalized_snapshot


class DecisionRuntime:
    def __init__(self, recorder, provider=None):
        self.recorder = recorder
        self.provider = provider or OpenAIExpertReasoningProvider()
        self._lock = Lock()
        self._current = None
        self.last_error = None

    def evaluate(self, options, structures, families, *, now=None, position=None):
        snapshot = normalized_snapshot(options, structures, families, now=now, position=position)
        deterministic = four_way(snapshot)
        snapshot["evaluation_trigger"] = {
            "regimes": {k: v["regime"] for k, v in deterministic["regimes"].items()},
            "impulse": deterministic["four_way_reset"],
            "candidate": [(c["instrument"], c["side"]) for c in deterministic["candidates"] if c["shadow_candidate"]],
            "position": position,
        }
        snapshot.pop("snapshot_id")
        snapshot["snapshot_id"] = snapshot_digest(snapshot)
        expert = self.provider.evaluate(snapshot)
        final = reconcile(snapshot, deterministic, expert)
        output = {"schema_version": "1.0", "timestamp": snapshot["timestamp"],
                  "snapshot_id": snapshot["snapshot_id"], "feed_fresh": all(i["fresh"] for i in snapshot["indices"].values()),
                  "missing_data": snapshot["missing_data"], "mode": "shadow",
                  "deterministic": deterministic, "final": final,
                  "expert_provider_status": self.provider.status()}
        try:
            sample_id = self.recorder.record_duel({"state": "EXPERT_REVIEW", "readiness": {"live_authorization": False}},
                {"status": "EXPERT_REVIEW", "authorization": "NONE", "expert_review": output}, snapshot)
            output["audit_sample_id"] = sample_id
            output["audit_status"] = "RECORDED"
        except Exception:
            output["audit_status"] = "UNAVAILABLE"
        with self._lock:
            self._current = deepcopy(output)
            self.last_error = None
        return output

    def current(self):
        with self._lock:
            output = deepcopy(self._current)
        if output is None:
            return {"schema_version": "1.0", "status": "PENDING", "mode": "shadow",
                    "timestamp": None, "feed_fresh": False, "missing_data": ["observer_snapshot"],
                    "deterministic": None, "final": {"action": "NO_EDGE", "read_only": True,
                    "auto_execution": False, "calibrated_probability": None, "calibration_status": "UNCALIBRATED"},
                    "expert_provider_status": self.provider.status()}
        from datetime import datetime
        from .freshness import IST
        age = (datetime.now(IST)-datetime.fromisoformat(output["timestamp"])).total_seconds()
        output["runtime_error"] = self.last_error
        output["age_seconds"] = age
        if not 0 <= age <= 60:
            output["feed_fresh"] = False
            output["missing_data"] = sorted(set(output["missing_data"]+["stale_decision"]))
            if output["final"]["action"] != "EXIT":
                output["final"]["action"] = "PROTECT" if output["final"]["risk"]["action"] in ("HOLD", "PROTECT") else "NO_EDGE"
        return output

    def history(self, limit=50):
        # Filter in SQL, so market-observation rows cannot hide older expert records.
        with self.recorder._connect() as db:
            import json
            rows = db.execute("SELECT id,decision,outcome,labelled_at FROM validation_samples WHERE state=? ORDER BY id DESC LIMIT ?",
                              ("EXPERT_REVIEW", max(1, min(limit, 200)))).fetchall()
        return [{"audit_sample_id": row[0], "evaluation": json.loads(row[1])["expert_review"],
                 "later_validation_outcome": json.loads(row[2]) if row[2] else None, "labelled_at": row[3]} for row in rows]
