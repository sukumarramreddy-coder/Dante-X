from __future__ import annotations
import json, os, sqlite3
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import Lock
from zoneinfo import ZoneInfo
from typing import Any

IST=ZoneInfo("Asia/Kolkata")
DEFAULT_DB=os.getenv("DANTEX_VALIDATION_DB","/tmp/dantex-validation.sqlite3")

class ValidationRecorder:
    """SQLite-backed SHADOW recorder. Set DANTEX_VALIDATION_DB to a persistent disk path in production."""
    def __init__(self,path:str=DEFAULT_DB):
        self.path=path; self._lock=Lock()
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self._init()
    def _connect(self):
        return sqlite3.connect(self.path,timeout=10)
    def _init(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS validation_samples(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              recorded_at TEXT NOT NULL,
              state TEXT,
              family_counts TEXT,
              readiness TEXT,
              decision TEXT
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_validation_recorded_at ON validation_samples(recorded_at)")
    def record_duel(self,families:dict[str,Any],decision:dict[str,Any]|None=None)->None:
        now=datetime.now(IST).isoformat()
        with self._lock,self._connect() as db:
            db.execute("INSERT INTO validation_samples(recorded_at,state,family_counts,readiness,decision) VALUES(?,?,?,?,?)",
              (now,families.get("state"),json.dumps(deepcopy(families.get("family_counts"))),
               json.dumps(deepcopy(families.get("readiness"))),json.dumps(deepcopy(decision))))
    def record(self,payload:dict[str,Any])->None:
        self.record_duel(payload,None)
    def status(self)->dict[str,Any]:
        with self._connect() as db:
            count,first,last=db.execute("SELECT COUNT(*),MIN(recorded_at),MAX(recorded_at) FROM validation_samples").fetchone()
        persistent=not self.path.startswith("/tmp/")
        return {"samples":count,"first":first,"last":last,"persistent":persistent,
          "storage":"sqlite","path":self.path if persistent else "ephemeral-runtime-disk",
          "mode":"shadow",
          "note":"SQLite validation history; persistence across Render restarts requires DANTEX_VALIDATION_DB on a persistent disk."}

validation_recorder=ValidationRecorder()
