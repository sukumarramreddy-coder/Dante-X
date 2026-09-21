from __future__ import annotations
from typing import Any

def shadow_decision(families: dict[str,Any], readiness: dict[str,Any], nifty: dict[str,Any]) -> dict[str,Any]:
    """Translate evidence into an auditable SHADOW plan; never places orders."""
    state=families.get("state","NO_EDGE")
    if not readiness.get("live_evidence_ready"):
        return {"status":"NO_SETUP","authorization":"NONE","reason":"required live evidence not fresh"}
    if state not in {"CE_EVIDENCE","PE_EVIDENCE"}:
        return {"status":"NO_SETUP","authorization":"NONE","reason":f"family consensus {state}"}
    side="CE" if state=="CE_EVIDENCE" else "PE"
    rows=nifty.get("strikes") or []
    candidates=[]
    for r in rows:
        leg=r.get("call" if side=="CE" else "put") or {}
        q=leg.get("quality") or {}
        spread=leg.get("spread_pct")
        if leg.get("ltp") and q.get("execution_score",0)>=50 and spread is not None and spread<=2:
            candidates.append((q.get("execution_score",0),-spread,r.get("strike"),leg))
    if not candidates:
        return {"status":"NO_SETUP","authorization":"NONE","direction":side,"reason":"no executable option contract"}
    _,_,strike,leg=max(candidates)
    premium=float(leg["ltp"])
    # Shadow-only premium geometry. Structural underlying invalidation remains required before real authorization.
    stop=round(premium*.85,2); t1=round(premium*1.20,2); t2=round(premium*1.35,2)
    risk=round(premium-stop,2); rr=round((t1-premium)/risk,2) if risk>0 else None
    return {"status":"DETECTED","authorization":"SHADOW_ONLY","direction":side,
      "contract":{"strike":strike,"expiry":nifty.get("expiry"),"instrument_key":leg.get("instrument_key")},
      "reference_entry":round(premium,2),"reference_stop":stop,"reference_t1":t1,"reference_t2":t2,
      "reference_rr_t1":rr,"note":"Illustrative shadow geometry; ARMED requires structural trigger, sizing, costs and calibrated validation."}
