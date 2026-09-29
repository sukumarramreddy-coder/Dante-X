from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any
from .outcome_labeler import label_from_path

IST=ZoneInfo("Asia/Kolkata")

class OutcomeTracker:
    """Tracks future observed option premiums for local SHADOW samples."""
    def __init__(self, recorder, horizon_minutes:int=30):
        self.recorder=recorder; self.horizon=timedelta(minutes=horizon_minutes)
        self.paths:dict[int,list[dict[str,Any]]]={}
    def observe(self, option_snapshots:dict[str,dict[str,Any]])->int:
        now=datetime.now(IST); labelled=0
        for s in self.recorder.unlabelled(200):
            decision=s.get("decision") or {}
            if (decision.get("status") or decision.get("state")) not in {"DETECTED","ARMED","GO"}:continue
            contract=decision.get("contract") or {}; key=contract.get("instrument_key")
            if not key:continue
            premium=None
            for snap in option_snapshots.values():
                if snap.get("evidence_eligible") is not True:continue
                for row in snap.get("strikes") or []:
                    for legname in ("call","put"):
                        leg=row.get(legname) or {}
                        if leg.get("instrument_key")==key:
                            premium=leg.get("ltp");break
                    if premium is not None:break
                if premium is not None:break
            if premium is not None:self.paths.setdefault(s["id"],[]).append({"at":now.isoformat(),"premium":premium})
            try:started=datetime.fromisoformat(s["recorded_at"])
            except Exception:continue
            if now-started>=self.horizon:
                outcome=label_from_path(s,self.paths.get(s["id"],[]))
                if outcome is not None:
                    self.recorder.label(s["id"],outcome); self.paths.pop(s["id"],None); labelled+=1
        return labelled
