"""Persistent 20-session fit / 10-session untouched validation for manual signals.

No orders, online refits of the validation model, or calendar-based promotion.
The model is deliberately small: beta-smoothed frequency by side/score band.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
import hashlib
import json
from math import log, sqrt
import os
from pathlib import Path
import sqlite3
import tempfile
from threading import RLock
from zoneinfo import ZoneInfo

from .meta_labels import triple_barrier
from .probability import finite_number

IST = ZoneInfo("Asia/Kolkata")
VERSION = "learning-30-v1"
TARGET_SESSIONS = 30
TRAIN_SESSIONS = 20
MIN_DAILY_LABELS = 5
MIN_TRAIN = 100
MIN_VALIDATION = 50
MIN_BAND = 20
EVENT = "T1_BEFORE_STOP_30M_SESSION"


def timestamp(value):
    at = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("aware timestamp required")
    return at.astimezone(IST)


def band(decision):
    return f'{decision["direction"]}:{min(9, int(decision["probability"] // 10))}'


def fit(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["band"]].append(row)
    return {key: {"samples": len(group), "wins": sum(r["outcome"] for r in group),
                  "probability": min(.65, max(.20, (sum(r["outcome"] for r in group) + 5) / (len(group) + 10)))}
            for key, group in sorted(groups.items())}


class LearningWindow:
    def __init__(self, path, *, durable=False):
        self.path = str(path)
        self.durable = durable
        self.lock = RLock()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS learning_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS learning_events (
                    id TEXT PRIMARY KEY, day TEXT NOT NULL, as_of TEXT NOT NULL,
                    deadline TEXT NOT NULL, phase TEXT NOT NULL, payload TEXT NOT NULL,
                    result TEXT, evidence TEXT);
                CREATE INDEX IF NOT EXISTS learning_days ON learning_events(day);
            """)
            db.execute("INSERT OR IGNORE INTO learning_meta VALUES ('version', ?)", (VERSION,))
            db.execute("INSERT OR IGNORE INTO learning_meta VALUES ('started_at', ?)",
                       (datetime.now(IST).isoformat(),))

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _meta(self, db, key):
        row = db.execute("SELECT value FROM learning_meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def _put(self, db, key, value):
        db.execute("INSERT OR REPLACE INTO learning_meta VALUES (?,?)", (key, json.dumps(value, sort_keys=True)))

    def _rows(self, db):
        return [{**json.loads(payload), "id": rid, "day": day, "phase": phase,
                 "result": json.loads(result) if result else None}
                for rid, day, phase, payload, result in db.execute(
                    "SELECT id,day,phase,payload,result FROM learning_events ORDER BY as_of")]

    def _advance(self, db, now):
        rows = self._rows(db)
        # Only completed prior sessions count. A noisy/empty/partial day cannot
        # advance the window merely because the exchange opened.
        valid = [r for r in rows if r["day"] < now.date().isoformat()
                 and (r["result"] or {}).get("status") in {"TARGET", "STOP", "TIMEOUT"}]
        train_counts = Counter(r["day"] for r in valid if r["phase"] == "TRAIN")
        train_days = sorted(day for day, n in train_counts.items() if n >= MIN_DAILY_LABELS)[:TRAIN_SESSIONS]
        model = self._meta(db, "model")
        if model is None and len(train_days) == TRAIN_SESSIONS:
            training = [{**r, "outcome": r["result"]["outcome"]} for r in valid if r["phase"] == "TRAIN"]
            model = {"bands": fit(training), "sessions": train_days, "frozen_at": now.isoformat(),
                     "samples": len(training), "base_rate": sum(r["outcome"] for r in training) / len(training),
                     "event": EVENT, "version": VERSION}
            model["sha256"] = hashlib.sha256(json.dumps(model, sort_keys=True).encode()).hexdigest()
            self._put(db, "model", model)
        validation_counts = Counter(r["day"] for r in valid if r["phase"] == "VALIDATE")
        validation_days = sorted(day for day, n in validation_counts.items() if n >= MIN_DAILY_LABELS)[:10]
        return rows, valid, train_days, validation_days, model

    def admit(self, decision, *, now=None):
        now = timestamp(now or datetime.now(IST))
        if (decision.get("status") != "DETECTED" or decision.get("authorization") != "SHADOW_ONLY"
                or decision.get("probability_status") != "PROVISIONAL"
                or not finite_number(decision.get("probability"))
                or not 20 <= decision["probability"] <= 60
                or (decision.get("probability_review") or {}).get("fresh_evidence") is not True):
            return None
        contract = decision.get("contract") or {}
        if not contract.get("instrument_key") or not contract.get("expiry"):
            return None
        # First full minute after observation; no partially observed entry bar.
        at = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        close = at.replace(hour=15, minute=30)
        if at.weekday() >= 5 or at.hour < 9 or at < at.replace(hour=9, minute=15) or at >= close:
            return None
        deadline = min(at + timedelta(minutes=30), close)
        if deadline - at < timedelta(minutes=30):
            return None
        with self.lock, self.connect() as db:
            _, _, _, validation_days, model = self._advance(db, now)
            if len(validation_days) >= 10:
                return None  # Frozen validation never becomes an expanding test set.
            if db.execute("SELECT 1 FROM learning_events WHERE deadline>?", (at.isoformat(),)).fetchone():
                return None  # Global 30m embargo, including correlated indices.
            phase = "VALIDATE" if model else "TRAIN"
            key = band(decision)
            fitted = (model or {}).get("bands", {}).get(key)
            # Unsupported bands cannot enter validation or be published.
            if model and (not fitted or fitted["samples"] < MIN_BAND):
                return None
            payload = {"decision": decision, "band": key, "as_of": at.isoformat(),
                       "predicted_at": now.isoformat(), "contract": contract["instrument_key"],
                       "baseline": decision["probability"] / 100,
                       "prediction": fitted["probability"] if fitted else None,
                       "model_sha256": model["sha256"] if model else None,
                       "model_frozen_at": model["frozen_at"] if model else None}
            rid = hashlib.sha256(f'{VERSION}:{at.isoformat()}:{payload["contract"]}'.encode()).hexdigest()
            db.execute("INSERT OR IGNORE INTO learning_events VALUES (?,?,?,?,?,?,NULL,NULL)",
                       (rid, at.date().isoformat(), at.isoformat(), deadline.isoformat(), phase,
                        json.dumps(payload, allow_nan=False)))
            return rid

    def pending(self, now=None):
        now = timestamp(now or datetime.now(IST))
        with self.connect() as db:
            return [{"id": rid, **json.loads(payload)} for rid, payload in db.execute(
                "SELECT id,payload FROM learning_events WHERE result IS NULL AND deadline<=? ORDER BY as_of LIMIT 20",
                (now.isoformat(),))]

    def resolve(self, rid, bars, *, now=None):
        now = timestamp(now or datetime.now(IST))
        with self.lock, self.connect() as db:
            row = db.execute("SELECT payload,result,deadline FROM learning_events WHERE id=?", (rid,)).fetchone()
            if not row or row[1] is not None:
                return False
            if now < timestamp(row[2]):
                return False
            payload = json.loads(row[0])
            d = payload["decision"]
            result = triple_barrier(contract=payload["contract"], as_of=timestamp(payload["as_of"]),
                                    entry=d["reference_entry"], stop=d["reference_stop"], target=d["reference_t1"],
                                    bars=bars, evaluated_at=now)
            # Fixed conservative *hypothetical* cost stress: 2% of entry premium.
            # Timeouts conservatively lose the full stop. This is not a fill/P&L.
            if result["outcome"] is not None:
                risk = d["reference_entry"] - d["reference_stop"]
                gross = d["reference_t1"] - d["reference_entry"] if result["outcome"] else -risk
                result["stressed_return_r"] = (gross - .02 * d["reference_entry"]) / risk
            evidence = [{**b, "at": timestamp(b["at"]).isoformat()} for b in bars]
            db.execute("UPDATE learning_events SET result=?,evidence=? WHERE id=? AND result IS NULL",
                       (json.dumps(result, allow_nan=False), json.dumps(evidence, allow_nan=False), rid))
            return True

    def _report(self, db, now):
        rows, valid, train_days, val_days, model = self._advance(db, now)
        train = [r for r in valid if r["phase"] == "TRAIN"]
        # Partial sessions don't count toward 30, but their valid outcomes must
        # still affect evaluation: never select only high-coverage/winning days.
        val = [r for r in valid if r["phase"] == "VALIDATE"
               and (len(val_days) < 10 or r["day"] <= val_days[-1])]
        blockers = []
        if len(train_days) < 20:
            blockers.append(f"training sessions {len(train_days)}/20")
        if len(val_days) < 10:
            blockers.append(f"untouched validation sessions {len(val_days)}/10")
        if len(train) < MIN_TRAIN or len(val) < MIN_VALIDATION:
            blockers.append("need at least 100 training and 50 validation outcomes")
        if not self.durable:
            blockers.append("learning store is not verified durable")
        metrics = None
        supported = []
        if val:
            brier = sum((r["prediction"] - r["result"]["outcome"]) ** 2 for r in val) / len(val)
            baseline = sum((r["baseline"] - r["result"]["outcome"]) ** 2 for r in val) / len(val)
            constant = sum((model["base_rate"] - r["result"]["outcome"]) ** 2 for r in val) / len(val)
            loss = -sum(log(r["prediction"] if r["result"]["outcome"] else 1-r["prediction"]) for r in val) / len(val)
            error = 0
            reliability = []
            for key in sorted({r["band"] for r in val}):
                group = [r for r in val if r["band"] == key]
                observed = sum(r["result"]["outcome"] for r in group) / len(group)
                predicted = group[0]["prediction"]
                error += len(group) * abs(observed - predicted) / len(val)
                reliability.append({"band": key, "samples": len(group), "predicted": predicted, "observed": observed})
                if len(group) >= 20 and abs(observed - predicted) <= .10:
                    supported.append(key)
            daily = [sum(r["result"]["stressed_return_r"] for r in val if r["day"] == day) /
                     sum(r["day"] == day for r in val) for day in sorted({r["day"] for r in val})]
            mean = sum(daily) / len(daily)
            # t(9) ~ 2.262; conservative fixed multiplier 2.3 for ten held-out days.
            se = sqrt(sum((x-mean)**2 for x in daily) / (len(daily)-1) / len(daily)) if len(daily) > 1 else 1e9
            lower = mean - 2.3 * se
            metrics = {"brier": brier, "baseline_brier": baseline, "constant_brier": constant,
                       "log_loss": loss, "calibration_error": error, "reliability": reliability,
                       "stressed_daily_mean_r": mean, "stressed_daily_lower_bound_r": lower}
            if brier >= baseline or brier > constant + .01:
                blockers.append("calibrator has not beaten the incumbent / matched constant baseline")
            if error > .10 or not supported:
                blockers.append("calibration error or per-band validation support insufficient")
            if lower <= 0:
                blockers.append("cost-stressed daily return lower bound is not positive")
        # Store version/target changes fail closed, including after a restart.
        version = db.execute("SELECT value FROM learning_meta WHERE key='version'").fetchone()[0]
        if version != VERSION:
            blockers.append("learning store version mismatch")
        if model and timestamp(model["frozen_at"]) > now:
            blockers.append("model timestamp is in the future")
        if val_days and (now.date() - datetime.fromisoformat(val_days[-1]).date()).days > 30:
            blockers.append("validation is more than 30 calendar days old; new reviewed window required")
        ready = not blockers
        state = "SIGNALS_LIVE" if ready else "VALIDATION_FAILED" if len(val_days) == 10 else "VALIDATING" if model else "LEARNING"
        preview = model["bands"] if model else fit([{**r, "outcome": r["result"]["outcome"]} for r in train])
        return {"version": VERSION, "state": state, "target_sessions": 30,
                "completed_sessions": len(train_days) + len(val_days), "training_sessions": train_days,
                "validation_sessions": val_days, "minimum_outcomes_per_session": MIN_DAILY_LABELS,
                "training_samples": len(train), "validation_samples": len(val),
                "pending_samples": sum(r["result"] is None for r in rows),
                "censored_samples": sum((r["result"] or {}).get("status") == "CENSORED" for r in rows),
                "observed_sessions": len({r["day"] for r in rows}), "learned_bands": preview,
                "model_sha256": model["sha256"] if model else None, "supported_bands": supported,
                "metrics": metrics, "blockers": blockers, "calibration_ready": ready,
                "auto_execution": False, "mode": "signals_only" if ready else "shadow",
                "live_orders": False, "durable": self.durable,
                "collection": self._meta(db, "collection"),
                "event": EVENT, "cost_model": "stress_2pct_entry_v1; hypothetical, no fills",
                "note": "30 qualifying sessions, not calendar days. Failed validation stays shadow; no automatic refit on holdout."}

    def report(self, now=None):
        with self.lock, self.connect() as db:
            return self._report(db, timestamp(now or datetime.now(IST)))

    def record_collection(self, decision, now):
        with self.lock, self.connect() as db:
            self._put(db, "collection", {"at": timestamp(now).isoformat(),
                      "status": decision.get("status", "NO_DATA"),
                      "reason": decision.get("reason", "awaiting eligible non-overlapping setup"),
                      "fresh_evidence": (decision.get("probability_review") or {}).get("fresh_evidence", False)})

    def publish(self, decision, *, now=None):
        """Only a separate manual-signal field is promoted. Execution is untouched."""
        now = timestamp(now or datetime.now(IST))
        report = self.report(now)
        result = {"status": "WAIT", "calibration_ready": False, "auto_execution": False,
                  "authorization": "NONE", "blockers": report["blockers"]}
        if (not report["calibration_ready"] or decision.get("status") != "DETECTED"
                or decision.get("authorization") != "SHADOW_ONLY"
                or (decision.get("probability_review") or {}).get("fresh_evidence") is not True
                or decision.get("probability_status") != "PROVISIONAL"):
            return result
        key = band(decision)
        if key not in report["supported_bands"]:
            return {**result, "blockers": ["current score/side band has not passed validation"]}
        return {"status": "VALIDATED_SIGNAL", "calibration_ready": True,
                "calibrated_probability": round(100 * report["learned_bands"][key]["probability"], 2),
                "unit": "percent", "model_sha256": report["model_sha256"], "event": EVENT,
                "authorization": "MANUAL_REVIEW_ONLY", "auto_execution": False,
                "as_of": now.isoformat(), "expires_at": (now + timedelta(seconds=60)).isoformat(),
                "live_orders": False, "decision": decision}


def learning_from_env():
    path = Path(os.getenv("DANTEX_LEARNING_DB", str(Path(tempfile.gettempdir()) / "dantex-learning.sqlite3"))).resolve()
    temporary = any(path == p or p in path.parents for p in
                    (Path(tempfile.gettempdir()).resolve(), Path('/tmp').resolve(), Path('/var/tmp').resolve()))
    durable = os.getenv("DANTEX_LEARNING_DURABLE", "false").lower() == "true" and not temporary
    return LearningWindow(path, durable=durable)
