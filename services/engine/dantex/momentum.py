from __future__ import annotations
from typing import Any

def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period: return None
    k=2/(period+1); e=sum(values[:period])/period
    for v in values[period:]: e=v*k+e*(1-k)
    return e

def _atr(rows: list[dict[str, Any]], period: int=14) -> float | None:
    if len(rows) < period+1: return None
    tr=[]
    for i in range(1,len(rows)):
        h,l,pc=rows[i]["high"],rows[i]["low"],rows[i-1]["close"]
        tr.append(max(h-l,abs(h-pc),abs(l-pc)))
    return sum(tr[-period:])/period

def momentum_family(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Short-horizon velocity/impulse family. Descriptive; never authorizes trades."""
    if len(rows) < 21:
        return {"state":"UNAVAILABLE","ce":0.0,"pe":0.0,"reasons":["insufficient candles"]}
    # Provider index bars can contain synthetic/flat intervals. Do not interpret
    # a closing print after a long flat run as genuine multi-minute momentum.
    tail=rows[-20:]
    flat_pairs=sum(float(a["close"]) == float(b["close"]) for a,b in zip(tail,tail[1:]))
    flat_ratio=flat_pairs/max(len(tail)-1,1)
    zero_volume_ratio=sum(float(r.get("volume") or 0)==0 for r in tail)/len(tail)
    if flat_ratio >= 0.5 and zero_volume_ratio >= 0.9:
        return {"state":"DATA_QUALITY_BLOCK","ce":0.0,"pe":0.0,
                "metrics":{"flat_pair_ratio":round(flat_ratio,3),"zero_volume_ratio":round(zero_volume_ratio,3)},
                "reasons":["synthetic/flat index bars make short-horizon velocity unreliable"]}
    closes=[float(r["close"]) for r in rows]
    last=closes[-1]; atr=_atr(rows) or 0.0
    d3=last-closes[-4]; d10=last-closes[-11]
    e9=_ema(closes,9); e20=_ema(closes,20)
    ce=pe=0.0; reasons=[]
    threshold=max(atr*.75,0.01)
    if d3>threshold and d10>0: ce+=1; reasons.append("positive short-horizon velocity")
    elif d3 < -threshold and d10<0: pe+=1; reasons.append("negative short-horizon velocity")
    if e9 is not None and e20 is not None:
        if last>e9>e20: ce+=1; reasons.append("price/EMA momentum aligned up")
        elif last<e9<e20: pe+=1; reasons.append("price/EMA momentum aligned down")
    # Recent range expansion is supporting context, not an independent direction vote.
    recent=max(float(r["high"]) for r in rows[-5:])-min(float(r["low"]) for r in rows[-5:])
    if atr and recent >= atr*3: reasons.append("recent range expansion")
    state="NEUTRAL"
    if ce and pe: state="CONFLICT"
    elif ce: state="CE"
    elif pe: state="PE"
    return {"state":state,"ce":min(ce,2.0),"pe":min(pe,2.0),
            "metrics":{"delta_3m":round(d3,2),"delta_10m":round(d10,2),"atr14":round(atr,2) if atr else None,
                       "recent_5m_range":round(recent,2)},
            "reasons":reasons or ["no momentum edge"]}

def cross_index_momentum(nifty: dict[str, Any], bank: dict[str, Any]) -> dict[str, Any]:
    ns=nifty.get("state"); bs=bank.get("state")
    if ns=="CE" and bs=="CE": return {"state":"CE","ce":1.5,"pe":0.0,"reasons":["NIFTY and BANKNIFTY momentum confirm up"]}
    if ns=="PE" and bs=="PE": return {"state":"PE","ce":0.0,"pe":1.5,"reasons":["NIFTY and BANKNIFTY momentum confirm down"]}
    if ns in {"CE","PE"} and bs in {"CE","PE"} and ns!=bs:
        return {"state":"CONFLICT","ce":0.0,"pe":0.0,"reasons":["NIFTY/BANKNIFTY momentum divergence"]}
    return {"state":"NEUTRAL","ce":0.0,"pe":0.0,"reasons":["cross-index momentum not confirmed"]}
