from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .audit import AuditRecord, SignalEvent, TradeOutcome
from .domain import Signal


class SignalStore:
    """Small durable audit store. Provider-agnostic and replaceable by Postgres later."""

    def __init__(self, path: str | Path = "dantex.db") -> None:
        self.path = str(path)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS signals (signal_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, signal_id TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outcomes (signal_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)

    def save_signal(self, signal: Signal) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO signals(signal_id,payload) VALUES (?,?)",
                (signal.signal_id, signal.model_dump_json()),
            )

    def append_event(self, event: SignalEvent) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO events(signal_id,payload) VALUES (?,?)",
                (event.signal_id, event.model_dump_json()),
            )

    def save_outcome(self, outcome: TradeOutcome) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO outcomes(signal_id,payload) VALUES (?,?)",
                (outcome.signal_id, outcome.model_dump_json()),
            )

    def get(self, signal_id: str) -> AuditRecord | None:
        with self._connect() as db:
            signal_row = db.execute(
                "SELECT payload FROM signals WHERE signal_id=?", (signal_id,)
            ).fetchone()
            if signal_row is None:
                return None
            event_rows = db.execute(
                "SELECT payload FROM events WHERE signal_id=? ORDER BY id", (signal_id,)
            ).fetchall()
            outcome_row = db.execute(
                "SELECT payload FROM outcomes WHERE signal_id=?", (signal_id,)
            ).fetchone()
        return AuditRecord(
            signal=Signal.model_validate(json.loads(signal_row["payload"])),
            events=[SignalEvent.model_validate(json.loads(x["payload"])) for x in event_rows],
            outcome=TradeOutcome.model_validate(json.loads(outcome_row["payload"]))
            if outcome_row else None,
        )
