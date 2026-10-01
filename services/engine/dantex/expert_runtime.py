"""Reuse the observer and validation recorder; no second service or broker interface."""
from copy import deepcopy
from threading import Lock

from .expert_engine import four_way, reconcile
from .expert_provider import OpenAIExpertReasoningProvider, snapshot_digest
from .expert_snapshot import normalized_snapshot
from .probability import evidence_prior


class DecisionRuntime:
    def __init__(self, recorder, provider=None):
        self.recorder = recorder
        self.provider = provider or OpenAIExpertReasoningProvider()
        self._lock = Lock()
        self._current = None
        self.last_error = None
        # Retain the latest review as explicitly stale context after a restart.
        # Query-only access cannot change any validation row.
        try:
            import json
            from pathlib import Path
            import sqlite3
            with sqlite3.connect(Path(recorder.path).resolve().as_uri() + "?mode=ro", uri=True) as db:
                db.execute("PRAGMA query_only=ON")
                row = db.execute("SELECT id,decision FROM validation_samples WHERE state=? ORDER BY id DESC LIMIT 1",
                                 ("EXPERT_REVIEW",)).fetchone()
            if row:
                restored = json.loads(row[1])["expert_review"]
                if (not isinstance(restored, dict) or not isinstance(restored.get("timestamp"), str)
                        or not isinstance(restored.get("final"), dict)
                        or not isinstance(restored["final"].get("risk"), dict)):
                    raise ValueError("invalid stored review")
                restored.update(audit_sample_id=row[0], restored_from_audit=True)
                if not restored.get("probability_review"):
                    restored["probability_review"] = evidence_prior({}, {"live_evidence_ready": False,
                        "blocked_sources": ["historical_review_without_directional_family_provenance"]})
                self._current = restored
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
            self.last_error = "audit_context_restore_unavailable"

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
        readiness = dict(families.get("readiness") or {})
        readiness["live_evidence_ready"] = readiness.get("live_evidence_ready") is True and all(
            i["fresh"] for i in snapshot["indices"].values())
        probability_review = evidence_prior(families, readiness)
        probability_review["scope"] = "NIFTY directional preference with BANKNIFTY confirmation"
        output = {"schema_version": "1.0", "timestamp": snapshot["timestamp"],
                  "snapshot_id": snapshot["snapshot_id"], "feed_fresh": all(i["fresh"] for i in snapshot["indices"].values()),
                  "missing_data": snapshot["missing_data"], "mode": "shadow",
                  "deterministic": deterministic, "final": final,
                  "probability_review": probability_review,
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
        if output.get("restored_from_audit") is True or not 0 <= age <= 60:
            output["feed_fresh"] = False
            output["missing_data"] = sorted(set(output["missing_data"]+["stale_decision"]))
            if output.get("probability_review"):
                review = output["probability_review"]
                review.update(status="PRIOR_ONLY", fresh_evidence=False,
                              data_quality="STALE_OR_MISSING", evidence_strength=0.0)
                review["directional"].update(ce=50.0, pe=50.0)
                review["blocked_sources"] = sorted(set(review["blocked_sources"] + ["stale_decision"]))
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
