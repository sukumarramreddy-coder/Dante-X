from __future__ import annotations
import json, os, sqlite3, urllib.request, tempfile
from urllib.parse import urlsplit
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from zoneinfo import ZoneInfo
from typing import Any

IST=ZoneInfo("Asia/Kolkata")
DEFAULT_DB=os.getenv("DANTEX_VALIDATION_DB",str(Path(tempfile.gettempdir()) / "dantex-validation.sqlite3"))


class NoCredentialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("external sink redirect refused")


class ValidationRecorder:
    """SQLite SHADOW dataset for evidence, decisions and later outcome labels."""
    def __init__(self,path:str=DEFAULT_DB):
        self.path=path
        self._lock=Lock()
        self.last_external_write_at: datetime | None = None
        self.last_external_attempt_at: datetime | None = None
        self.last_external_error: str | None = None
        self.external_write_failures = 0
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self._init()
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
        if not url and not key:return False
        if not url or not key:raise ValueError("incomplete external sink configuration")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("external sink requires an HTTPS URL without credentials or query")
        self.last_external_attempt_at = datetime.now(timezone.utc)
        req=urllib.request.Request(url,data=json.dumps(row).encode(),method="POST",
            headers={"Content-Type":"application/json","apikey":key,
                     "Authorization":f"Bearer {key}","Prefer":"return=minimal"})
        with urllib.request.build_opener(NoCredentialRedirect()).open(req,timeout=8) as resp:
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
            wrote = self._external_write({"recorded_at":now,"state":families.get("state"),
              "family_counts":deepcopy(families.get("family_counts")),
              "readiness":deepcopy(families.get("readiness")),
              "decision":deepcopy(decision),"market_snapshot":deepcopy(market_snapshot),"source_sample_id":sample_id})
            if wrote:
                self.last_external_write_at = datetime.now(timezone.utc)
                self.last_external_error = None
        except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
            self.external_write_failures += 1
            self.last_external_error = type(exc).__name__
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
        external=bool(os.getenv("DANTEX_VALIDATION_REST_URL") or os.getenv("DANTEX_VALIDATION_REST_KEY"))
        # A pathname alone cannot prove a persistent volume. Explicit operator
        # attestation is required, and known temporary locations remain excluded.
        resolved = Path(self.path).resolve()
        temporary = self.path == ":memory:" or any(
            resolved == base or base in resolved.parents
            for base in (Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve(), Path("/var/tmp").resolve())
        )
        local_durable = os.getenv("DANTEX_VALIDATION_DURABLE", "").lower() == "true" and not temporary
        age = ((datetime.now(timezone.utc) - self.last_external_write_at).total_seconds()
               if self.last_external_write_at else None)
        external_healthy = external and age is not None and 0 <= age < 60 and self.last_external_error is None
        persistent = local_durable
        durable_ready = external_healthy if external else local_durable
        return {"samples":count,"labelled_samples":labelled or 0,"first":first,"last":last,
          "persistent":persistent,"external_configured":external,
          "durable_ready":durable_ready,"local_durable":local_durable,
          "external_healthy":external_healthy,
          "storage":"external+sqlite" if external else "sqlite",
          "path":"external-rest" if external else (self.path if persistent else "ephemeral-runtime-disk"),"mode":"shadow",
          "external_write":{"last_success_at":self.last_external_write_at.isoformat() if self.last_external_write_at else None,
                            "last_attempt_at":self.last_external_attempt_at.isoformat() if self.last_external_attempt_at else None,
                            "last_error":self.last_external_error,
                            "failures":self.external_write_failures},
          "calibration_ready":False,
          "note":"Outcome-capable SHADOW dataset. Statistical calibration remains disabled until sufficient labelled out-of-sample history exists."}

validation_recorder=ValidationRecorder()
