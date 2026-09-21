from __future__ import annotations
from collections import deque
from copy import deepcopy
from datetime import datetime
from threading import Lock
from zoneinfo import ZoneInfo
from typing import Any

IST=ZoneInfo("Asia/Kolkata")

class ValidationRecorder:
    """In-process bounded recorder. Persistent storage is a later deployment concern."""
    def __init__(self,maxlen:int=2000):
        self._rows=deque(maxlen=maxlen); self._lock=Lock()
    def record(self,payload:dict[str,Any])->None:
        row={"recorded_at":datetime.now(IST).isoformat(),
             "state":payload.get("state"),
             "family_counts":deepcopy(payload.get("family_counts")),
             "readiness":deepcopy(payload.get("readiness"))}
        with self._lock:self._rows.append(row)
    def status(self)->dict[str,Any]:
        with self._lock:
            return {"samples":len(self._rows),
                    "first":self._rows[0]["recorded_at"] if self._rows else None,
                    "last":self._rows[-1]["recorded_at"] if self._rows else None,
                    "persistent":False,"mode":"shadow",
                    "note":"Bounded runtime validation buffer; not sufficient for probability calibration."}

validation_recorder=ValidationRecorder()
