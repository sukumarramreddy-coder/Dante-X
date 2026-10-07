"""Autonomous paper desk. Fake money only. Never constructs a broker order."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
STARTING_CAPITAL = 1_000_000.0
DAILY_LOSS_LIMIT = 10_000.0
FIXED_QTY = 1


class PaperDesk:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def _init(self) -> None:
        with self._lock, self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS control (
                key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS paper_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                action TEXT NOT NULL,
                payload TEXT NOT NULL)""")
            db.execute("INSERT OR IGNORE INTO control(key, value) VALUES ('killed', '0')")
            db.execute("INSERT OR IGNORE INTO control(key, value) VALUES ('equity', ?)", (str(STARTING_CAPITAL),))
            db.execute("INSERT OR IGNORE INTO control(key, value) VALUES ('day', '')")
            db.execute("INSERT OR IGNORE INTO control(key, value) VALUES ('day_pnl', '0')")
            db.execute("INSERT OR IGNORE INTO control(key, value) VALUES ('position', '')")

    def _get(self, db, key: str) -> str:
        row = db.execute("SELECT value FROM control WHERE key=?", (key,)).fetchone()
        return row["value"] if row else ""

    def _set(self, db, key: str, value: str) -> None:
        db.execute("INSERT INTO control(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def kill(self, reason: str = "operator") -> dict:
        with self._lock, self._connect() as db:
            self._set(db, "killed", "1")
            self._flatten(db, reason="kill_switch")
            self._event(db, "KILL", {"reason": reason})
            return self._status(db)

    def release(self) -> dict:
        with self._lock, self._connect() as db:
            self._set(db, "killed", "0")
            self._event(db, "RELEASE", {})
            return self._status(db)

    def status(self) -> dict:
        with self._lock, self._connect() as db:
            return self._status(db)

    def _status(self, db) -> dict:
        position = self._get(db, "position")
        return {
            "mode": "paper",
            "money": "fake",
            "killed": self._get(db, "killed") == "1",
            "equity": float(self._get(db, "equity") or STARTING_CAPITAL),
            "day": self._get(db, "day"),
            "day_pnl": float(self._get(db, "day_pnl") or 0),
            "position": json.loads(position) if position else None,
            "mt5": "ASLEEP",
            "live_orders": False,
            "probability": "provisional_unchanged",
            "calibration_independent": True,
        }

    def _event(self, db, action: str, payload: dict) -> None:
        db.execute(
            "INSERT INTO paper_events(recorded_at, action, payload) VALUES (?, ?, ?)",
            (datetime.now(IST).isoformat(), action, json.dumps(payload)),
        )

    def _flatten(self, db, reason: str) -> None:
        raw = self._get(db, "position")
        if not raw:
            return
        position = json.loads(raw)
        self._set(db, "position", "")
        self._event(db, "FLAT", {"reason": reason, "position": position})

    def consider(self, decision: dict, *, now: datetime | None = None) -> dict:
        """Record a paper action from an existing shadow decision. Never places a broker order."""
        now = (now or datetime.now(IST)).astimezone(IST)
        decision = decision or {}
        with self._lock, self._connect() as db:
            if self._get(db, "killed") == "1":
                self._event(db, "BLOCKED", {"reason": "kill_switch"})
                return {**self._status(db), "action": "BLOCKED", "reason": "kill_switch"}
            day = now.date().isoformat()
            if self._get(db, "day") != day:
                self._set(db, "day", day)
                self._set(db, "day_pnl", "0")
            if float(self._get(db, "day_pnl") or 0) <= -DAILY_LOSS_LIMIT:
                self._flatten(db, reason="daily_loss_limit")
                self._event(db, "BLOCKED", {"reason": "daily_loss_limit"})
                return {**self._status(db), "action": "BLOCKED", "reason": "daily_loss_limit"}
            status = decision.get("status") or decision.get("state")
            fresh = decision.get("fresh_evidence") is True
            prior = decision.get("probability_status") == "PRIOR_ONLY" or decision.get("status") == "PRIOR_ONLY"
            entry = decision.get("reference_entry")
            stop = decision.get("reference_stop")
            target = decision.get("reference_t1")
            eligible = status == "DETECTED" and fresh and not prior and _positive(entry, stop, target)
            if not eligible:
                reason = "no_fresh_detected_setup"
                self._event(db, "NO_TRADE", {"reason": reason, "status": status, "fresh": fresh})
                return {**self._status(db), "action": "NO_TRADE", "reason": reason}
            if self._get(db, "position"):
                return {**self._status(db), "action": "HOLD", "reason": "position_open"}
            position = {
                "side": decision.get("direction") or "CE",
                "entry": entry,
                "stop": stop,
                "target": target,
                "qty": FIXED_QTY,
                "opened_at": now.isoformat(),
                "money": "fake",
            }
            self._set(db, "position", json.dumps(position))
            self._event(db, "FILL", position)
            return {**self._status(db), "action": "FILL", "reason": "fresh_detected_setup"}


def _positive(*values) -> bool:
    try:
        return all(float(v) > 0 for v in values)
    except (TypeError, ValueError):
        return False


def mt5_shell() -> dict:
    """Present but unable to construct an order client."""
    return {
        "module": "metatrader5_shell",
        "state": "ASLEEP",
        "wake_allowed": False,
        "order_client": None,
        "reason": "asleep until paper measurement and 30-session calibration are complete",
        "live_orders": False,
    }
