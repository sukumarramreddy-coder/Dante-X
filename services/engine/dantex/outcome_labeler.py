from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

IST=ZoneInfo("Asia/Kolkata")

def _num(v):
    try:return float(v)
    except (TypeError,ValueError):return None

def label_from_path(sample:dict[str,Any], future_rows:list[dict[str,Any]])->dict[str,Any]|None:
    """Deterministic SHADOW label. No probability claims; requires observed future prices."""
    decision=sample.get("decision") or {}
    if (decision.get("status") or decision.get("state")) not in {"DETECTED","ARMED","GO"}:return {"eligible":False,"reason":"no directional shadow setup"}
    plan=decision.get("plan") or decision.get("execution") or decision
    entry=_num(plan.get("entry") or plan.get("reference_entry")); stop=_num(plan.get("stop") or plan.get("reference_stop")); t1=_num(plan.get("t1") or plan.get("reference_t1")); t2=_num(plan.get("t2") or plan.get("reference_t2"))
    if None in (entry,stop,t1,t2):return {"eligible":False,"reason":"execution geometry unavailable"}
    prices=[]
    for r in future_rows:
        p=_num(r.get("premium") or r.get("ltp") or r.get("price"))
        if p is not None:prices.append(p)
    if not prices:return None
    mfe=max(prices)-entry; mae=min(prices)-entry
    first="NONE"
    for p in prices:
        if p<=stop:first="STOP";break
        if p>=t2:first="T2";break
        if p>=t1:first="T1";break
    return {"eligible":True,"entry":entry,"stop":stop,"t1":t1,"t2":t2,
            "mfe":round(mfe,4),"mae":round(mae,4),"first_event":first,
            "observations":len(prices),"labelled_at":datetime.now(IST).isoformat(),
            "note":"descriptive shadow outcome; costs/slippage and OOS calibration are separate gates"}
