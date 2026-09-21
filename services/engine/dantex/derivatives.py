from __future__ import annotations
from typing import Any

def _sum(rows, side, key):
    return sum(float((r.get(side) or {}).get(key) or 0) for r in rows)

def derivatives_positioning_family(nifty: dict[str,Any], bank: dict[str,Any]) -> dict[str,Any]:
    """One bounded derivatives family; never count OI/PCR/IV as separate votes."""
    metrics={}; votes=[]; reasons=[]
    for label,snap in (("NIFTY",nifty),("BANKNIFTY",bank)):
        rows=snap.get("strikes") or []
        if not rows: continue
        call_oi=_sum(rows,"call","oi"); put_oi=_sum(rows,"put","oi")
        call_doi=_sum(rows,"call","oi_change"); put_doi=_sum(rows,"put","oi_change")
        civ=[(r.get("call") or {}).get("iv") for r in rows]; piv=[(r.get("put") or {}).get("iv") for r in rows]
        civ=[float(x) for x in civ if x is not None]; piv=[float(x) for x in piv if x is not None]
        pcr=put_oi/call_oi if call_oi else None
        skew=(sum(piv)/len(piv)-sum(civ)/len(civ)) if piv and civ else None
        metrics[label.lower()]={"pcr_oi":round(pcr,3) if pcr is not None else None,
          "call_oi_change":round(call_doi,1),"put_oi_change":round(put_doi,1),
          "put_minus_call_iv":round(skew,3) if skew is not None else None}
        # Conservative positioning interpretation: require OI-change and PCR agreement.
        if pcr is not None and pcr>=1.15 and put_doi>call_doi: votes.append("CE")
        elif pcr is not None and pcr<=0.85 and call_doi>put_doi: votes.append("PE")
        else: votes.append("NEUTRAL")
    dirs={v for v in votes if v!="NEUTRAL"}
    if len(dirs)>1: state="CONFLICT"
    elif dirs: state=next(iter(dirs))
    else: state="NEUTRAL"
    reasons.append("derivatives positioning synthesized across indices; OI/PCR/IV are not independent votes")
    return {"state":state,"ce":1.5 if state=="CE" else 0.0,"pe":1.5 if state=="PE" else 0.0,
      "metrics":metrics,"quality":{"indices":len(metrics)},"reasons":reasons}
