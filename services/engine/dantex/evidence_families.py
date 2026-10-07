from __future__ import annotations
from typing import Any

def _direction(ce: float, pe: float) -> str:
    if ce and pe: return "CONFLICT"
    if ce: return "CE"
    if pe: return "PE"
    return "NEUTRAL"

def structure_family(s: dict[str, Any] | None) -> dict[str, Any]:
    if not s or s.get("status") != "OK":
        return {"state":"UNAVAILABLE","ce":0.0,"pe":0.0,"reasons":[]}
    if s.get("evidence_eligible") is False:
        return {"state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
                "quality":{"freshness":s.get("freshness"),"session_date":s.get("session_date")},
                "reasons":["structure retained for context but blocked from live evidence"]}
    ce=pe=0.0; reasons=[]
    trend=s.get("trend"); opening=s.get("opening_range_state"); loc=s.get("location") or {}
    if trend=="BULLISH": ce+=1; reasons.append("bullish EMA alignment")
    elif trend=="BEARISH": pe+=1; reasons.append("bearish EMA alignment")
    if opening=="ABOVE_OPENING_RANGE": ce+=1; reasons.append("above opening-range high")
    elif opening=="BELOW_OPENING_RANGE": pe+=1; reasons.append("below opening-range low")
    if loc.get("vs_prior_high")=="ABOVE": ce+=1; reasons.append("above prior-day high")
    elif loc.get("vs_prior_low")=="BELOW": pe+=1; reasons.append("below prior-day low")
    if loc.get("vs_vwap")=="ABOVE": ce+=.5; reasons.append("above VWAP")
    elif loc.get("vs_vwap")=="BELOW": pe+=.5; reasons.append("below VWAP")
    ce,pe=min(ce,2.0),min(pe,2.0)
    return {"state":_direction(ce,pe),"ce":ce,"pe":pe,"reasons":reasons}

def options_family(s: dict[str, Any]) -> dict[str, Any]:
    state=(s.get("path_response") or {}).get("state"); ce=pe=0.0
    reasons=[f"option path {state or 'unavailable'}"]
    if state=="CE_STRENGTHENING": ce=2.0
    elif state=="PE_STRENGTHENING": pe=2.0
    elif state=="BULL_MOVE_REFUSED_BY_OPTIONS": pe=1.5
    elif state=="BEAR_MOVE_REFUSED_BY_OPTIONS": ce=1.5
    return {"state":_direction(ce,pe),"ce":ce,"pe":pe,"reasons":reasons}

def cross_index_family(nifty: dict[str, Any], bank: dict[str, Any]) -> dict[str, Any]:
    n=(nifty.get("path_response") or {}).get("spot_change")
    b=(bank.get("path_response") or {}).get("spot_change")
    ce=pe=0.0; reasons=[]
    if n is not None and b is not None:
        if n>0 and b>0: ce=1.5; reasons.append("both index paths up")
        elif n<0 and b<0: pe=1.5; reasons.append("both index paths down")
        elif n!=0 and b!=0: reasons.append("cross-index divergence")
    if not reasons: reasons.append("cross-index baseline unavailable")
    return {"state":_direction(ce,pe),"ce":ce,"pe":pe,"reasons":reasons}

def _synth_family(name: str, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Collapse correlated NIFTY/BANKNIFTY observations into one family vote."""
    ls, rs = left.get("state"), right.get("state")
    blocked = {"UNAVAILABLE", "STALE_CONTEXT", "DATA_QUALITY_BLOCK"}
    active = [x for x in (left, right) if x.get("state") not in blocked]
    reasons = [f"NIFTY: {r}" for r in left.get("reasons", [])] + [f"BANKNIFTY: {r}" for r in right.get("reasons", [])]
    if not active:
        state = "STALE_CONTEXT" if "STALE_CONTEXT" in {ls, rs} else "UNAVAILABLE"
        return {"state":state,"ce":0.0,"pe":0.0,"components":{"nifty":ls,"banknifty":rs},"reasons":reasons}
    dirs = {x.get("state") for x in active if x.get("state") in {"CE","PE","CONFLICT"}}
    if "CONFLICT" in dirs or ("CE" in dirs and "PE" in dirs):
        return {"state":"CONFLICT","ce":0.0,"pe":0.0,"components":{"nifty":ls,"banknifty":rs},"reasons":reasons}
    if dirs == {"CE"}:
        return {"state":"CE","ce":max(x.get("ce",0.0) for x in active),"pe":0.0,"components":{"nifty":ls,"banknifty":rs},"reasons":reasons}
    if dirs == {"PE"}:
        return {"state":"PE","ce":0.0,"pe":max(x.get("pe",0.0) for x in active),"components":{"nifty":ls,"banknifty":rs},"reasons":reasons}
    return {"state":"NEUTRAL","ce":0.0,"pe":0.0,"components":{"nifty":ls,"banknifty":rs},"reasons":reasons}

def recompute_consensus(families: dict[str, dict[str, Any]]) -> dict[str, Any]:
    directional=[v for v in families.values() if v.get("state") in {"CE","PE","CONFLICT"}]
    c=sum(v.get("state")=="CE" for v in directional); p=sum(v.get("state")=="PE" for v in directional)
    x=sum(v.get("state")=="CONFLICT" for v in directional)
    state="CONFLICT" if x or (c and p) else "CE_EVIDENCE" if c>=2 else "PE_EVIDENCE" if p>=2 else "NO_EDGE"
    return {"state":state,"family_counts":{"ce":c,"pe":p,"conflict":x,"directional":len(directional)}}

def evidence_families(nifty: dict[str, Any], bank: dict[str, Any],
                      nifty_structure: dict[str, Any] | None,
                      bank_structure: dict[str, Any] | None) -> dict[str, Any]:
    ns=structure_family(nifty_structure); bs=structure_family(bank_structure)
    no=options_family(nifty); bo=options_family(bank)
    families={
      "structure_location":_synth_family("structure_location",ns,bs),
      "options_response":_synth_family("options_response",no,bo),
      "cross_index":cross_index_family(nifty,bank),
    }
    consensus=recompute_consensus(families)
    return {"state":consensus["state"],"families":families,
      "family_counts":consensus["family_counts"],"authorization":"NONE",
      "note":"Consensus counts independent evidence families, not per-index correlated observations; not calibrated probability or trade authorization."}
