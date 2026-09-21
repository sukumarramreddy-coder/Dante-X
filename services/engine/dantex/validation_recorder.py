from __future__ import annotations
import json, os, sqlite3, urllib.request
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import Lock
from zoneinfo import ZoneInfo
from typing import Any

IST=ZoneInfo("Asia/Kolkata")
DEFAULT_DB=os.getenv("DANTEX_VALIDATION_DB","/tmp/dantex-validation.sqlite3")

class ValidationRecorder:
    """SQLite SHADOW dataset for evidence, decisions and later outcome labels."""
    def __init__(self,path:str=DEFAULT_DB):
        self.path=path; self._lock=Lock(); Path(path).parent.mkdir(parents=True,exist_ok=True); self._init()
    def _connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.execute("PRAGMA journal_mode=WAL"); db.execute("PRAGMA synchronous=NORMAL")
        return db
    def _init(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS validation_samples(
              id INTEGER PRIMARY KEY AUTOINCREMENT, recorded_at TEXT NOT NULL,
              state TEXT, family_counts TEXT, readiness TEXT, decision TEXT,
              market_snapshot TEXT, outcome TEXT, labelled_at TEXT)""")
            cols={r[1] for r in db.execute("PRAGMA table_info(validation_samples)")}
            for name,typ in (("market_snapshot","TEXT"),("outcome","TEXT"),("labelled_at","TEXT")):
                if name not in cols: db.execute(f"ALTER TABLE validation_samples ADD COLUMN {name} {typ}")
            db.execute("CREATE INDEX IF NOT EXISTS idx_validation_recorded_at ON validation_samples(recorded_at)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_validation_state ON validation_samples(state)")
    def _external_write(self,row:dict[str,Any])->bool:
        """Optional zero-cost durable sink. Compatible with Supabase REST when configured."""
        url=os.getenv("DANTEX_VALIDATION_REST_URL","").rstrip("/")
        key=os.getenv("DANTEX_VALIDATION_REST_KEY","")
        if not url or not key:return False
        req=urllib.request.Request(url,data=json.dumps(row).encode(),method="POST",
            headers={"Content-Type":"application/json","apikey":key,
                     "Authorization":f"Bearer {key}","Prefer":"return=minimal"})
        with urllib.request.urlopen(req,timeout=8) as resp:
            if resp.status not in (200,201,204):raise RuntimeError(f"external validation sink HTTP {resp.status}")
        return True
    def record_duel(self,families:dict[str,Any],decision:dict[str,Any]|None=None,market_snapshot:dict[str,Any]|None=None)->int:
        now=datetime.now(IST).isoformat()
        with self._lock,self._connect() as db:
            cur=db.execute("""INSERT INTO validation_samples
              (recorded_at,state,family_counts,readiness,decision,market_snapshot)
              VALUES(?,?,?,?,?,?)""",(now,families.get("state"),
              json.dumps(deepcopy(families.get("family_counts"))),
              json.dumps(deepcopy(families.get("readiness"))),
              json.dumps(deepcopy(decision)),json.dumps(deepcopy(market_snapshot))))
            sample_id=int(cur.lastrowid)
        # Local SQLite is always retained as a fallback; configured external
        # storage is the durable copy when Render's filesystem is ephemeral.
        try:
            self._external_write({"recorded_at":now,"state":families.get("state"),
              "family_counts":deepcopy(families.get("family_counts")),
              "readiness":deepcopy(families.get("readiness")),
              "decision":deepcopy(decision),"market_snapshot":deepcopy(market_snapshot)})
        except Exception:
            pass
        return sample_id
    def record(self,payload:dict[str,Any])->None:self.record_duel(payload,None)
    def label(self,sample_id:int,outcome:dict[str,Any])->None:
        with self._lock,self._connect() as db:
            db.execute("UPDATE validation_samples SET outcome=?,labelled_at=? WHERE id=?",
              (json.dumps(deepcopy(outcome)),datetime.now(IST).isoformat(),sample_id))
    def unlabelled(self,limit:int=200)->list[dict[str,Any]]:
        with self._connect() as db:
            rows=db.execute("""SELECT id,recorded_at,state,decision,market_snapshot
              FROM validation_samples WHERE outcome IS NULL ORDER BY id ASC LIMIT ?""",(limit,)).fetchall()
        out=[]
        for rid,ts,state,decision,snap in rows:
            out.append({"id":rid,"recorded_at":ts,"state":state,
              "decision":json.loads(decision) if decision else None,
              "market_snapshot":json.loads(snap) if snap else None})
        return out
    def recent(self,limit:int=100)->list[dict[str,Any]]:
        with self._connect() as db:
            rows=db.execute("""SELECT id,recorded_at,state,family_counts,readiness,decision,
              market_snapshot,outcome,labelled_at FROM validation_samples ORDER BY id DESC LIMIT ?""",(limit,)).fetchall()
        keys=("id","recorded_at","state","family_counts","readiness","decision","market_snapshot","outcome","labelled_at")
        out=[]
        for row in rows:
            item=dict(zip(keys,row))
            for k in ("family_counts","readiness","decision","market_snapshot","outcome"):
                if item[k]:
                    try:item[k]=json.loads(item[k])
                    except Exception:pass
            out.append(item)
        return out
    def status(self)->dict[str,Any]:
        with self._connect() as db:
            count,first,last,labelled=db.execute("""SELECT COUNT(*),MIN(recorded_at),
              MAX(recorded_at),SUM(CASE WHEN outcome IS NOT NULL THEN 1 ELSE 0 END)
              FROM validation_samples""").fetchone()
        external=bool(os.getenv("DANTEX_VALIDATION_REST_URL") and os.getenv("DANTEX_VALIDATION_REST_KEY"))
        persistent=external or not self.path.startswith("/tmp/")
        return {"samples":count,"labelled_samples":labelled or 0,"first":first,"last":last,
          "persistent":persistent,"storage":"external+sqlite" if external else "sqlite",
          "path":"external-rest" if external else (self.path if persistent else "ephemeral-runtime-disk"),"mode":"shadow",
          "calibration_ready":False,
          "note":"Outcome-capable SHADOW dataset. Statistical calibration remains disabled until sufficient labelled out-of-sample history exists."}

validation_recorder=ValidationRecorder()
