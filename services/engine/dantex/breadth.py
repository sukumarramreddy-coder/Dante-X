from __future__ import annotations

from typing import Any

# NIFTY 50 constituent keys are intentionally explicit: breadth must come from
# actual constituents, never be inferred from the index candle itself.
# Instrument keys use NSE_EQ ISIN form accepted by Upstox market quote APIs.
NIFTY_BREADTH_KEYS = [
    "NSE_EQ|INE002A01018","NSE_EQ|INE040A01034","NSE_EQ|INE090A01021",
    "NSE_EQ|INE009A01021","NSE_EQ|INE467B01029","NSE_EQ|INE062A01020",
    "NSE_EQ|INE018A01030","NSE_EQ|INE397D01024","NSE_EQ|INE154A01025",
    "NSE_EQ|INE030A01027","NSE_EQ|INE238A01034","NSE_EQ|INE021A01026",
    "NSE_EQ|INE044A01036","NSE_EQ|INE860A01027","NSE_EQ|INE101A01026",
]

def breadth_family(quotes: list[dict[str, Any]]) -> dict[str, Any]:
    """Participation family from a liquid NIFTY constituent basket.

    Uses day change versus previous close. This is breadth context, not a
    calibrated probability and never trade authorization.
    """
    usable=[]
    for q in quotes:
        ltp=q.get("ltp"); prev=q.get("prev_close")
        if isinstance(ltp,(int,float)) and isinstance(prev,(int,float)) and prev>0:
            usable.append((ltp-prev)/prev*100)
    if len(usable) < 10:
        return {"state":"UNAVAILABLE","ce":0.0,"pe":0.0,
                "quality":{"usable":len(usable),"required":10},
                "reasons":["insufficient constituent quotes"]}
    # A fully flat basket outside a live session is not genuine neutral breadth;
    # it is a closed-market/stale snapshot and must have zero evidentiary weight.
    if max(abs(x) for x in usable) < 0.01:
        return {"state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
                "metrics":{"advancers":0,"decliners":0,"flat":len(usable),
                           "participation_balance":0.0,"median_change_pct":0.0},
                "quality":{"usable":len(usable),"required":10,"freshness":"NON_MOVING_SNAPSHOT"},
                "reasons":["constituent basket is fully flat; breadth blocked outside live price discovery"]}
    adv=sum(x>0.05 for x in usable); dec=sum(x<-.05 for x in usable); flat=len(usable)-adv-dec
    ratio=(adv-dec)/len(usable)
    median=sorted(usable)[len(usable)//2]
    state="NEUTRAL"; ce=pe=0.0
    if ratio>=0.4 and median>0:
        state="CE"; ce=1.5
    elif ratio<=-0.4 and median<0:
        state="PE"; pe=1.5
    return {"state":state,"ce":ce,"pe":pe,
            "metrics":{"advancers":adv,"decliners":dec,"flat":flat,
                       "participation_balance":round(ratio,3),
                       "median_change_pct":round(median,3)},
            "quality":{"usable":len(usable),"required":10},
            "reasons":[
                "broad constituent participation up" if state=="CE" else
                "broad constituent participation down" if state=="PE" else
                "constituent participation mixed"
            ]}


# Sector indices are an independent participation/leadership diagnostic. They
# are deliberately explicit and read-only; missing provider keys fail closed.
SECTOR_INDEX_KEYS = {
    "BANK": "NSE_INDEX|Nifty Bank",
    "IT": "NSE_INDEX|Nifty IT",
    "AUTO": "NSE_INDEX|Nifty Auto",
    "FMCG": "NSE_INDEX|Nifty FMCG",
    "METAL": "NSE_INDEX|Nifty Metal",
    "PHARMA": "NSE_INDEX|Nifty Pharma",
    "REALTY": "NSE_INDEX|Nifty Realty",
    "ENERGY": "NSE_INDEX|Nifty Energy",
}

def sector_leadership_family(quotes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Cross-sector leadership from day change versus previous close.

    This measures whether risk appetite is broad or defensive/mixed. It is
    diagnostic until freshness is independently proven by the caller.
    """
    changes: dict[str, float] = {}
    for name, q in quotes.items():
        ltp=q.get("ltp"); prev=q.get("prev_close")
        if isinstance(ltp,(int,float)) and isinstance(prev,(int,float)) and prev>0:
            changes[name]=(ltp-prev)/prev*100
    if len(changes) < 5:
        return {"state":"UNAVAILABLE","ce":0.0,"pe":0.0,
                "quality":{"usable":len(changes),"required":5},
                "reasons":["insufficient sector-index quotes"]}
    vals=list(changes.values())
    if max(abs(x) for x in vals) < .01:
        return {"state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
                "metrics":{"changes_pct":{k:round(v,3) for k,v in changes.items()}},
                "quality":{"usable":len(changes),"freshness":"NON_MOVING_SNAPSHOT"},
                "reasons":["sector indices are fully flat; leadership blocked outside live price discovery"]}
    adv=sum(x>.05 for x in vals); dec=sum(x<-.05 for x in vals)
    ordered=sorted(changes.items(), key=lambda kv: kv[1], reverse=True)
    balance=(adv-dec)/len(vals)
    state="NEUTRAL"; ce=pe=0.0
    if balance >= .5:
        state="CE"; ce=1.5
    elif balance <= -.5:
        state="PE"; pe=1.5
    return {"state":state,"ce":ce,"pe":pe,
            "metrics":{"advancing_sectors":adv,"declining_sectors":dec,
                       "participation_balance":round(balance,3),
                       "leaders":[[k,round(v,3)] for k,v in ordered[:3]],
                       "laggards":[[k,round(v,3)] for k,v in ordered[-3:]]},
            "quality":{"usable":len(changes),"required":5},
            "reasons":["broad sector leadership positive" if state=="CE" else
                       "broad sector leadership negative" if state=="PE" else
                       "sector leadership mixed"]}


INDIA_VIX_KEY = "NSE_INDEX|India VIX"

def volatility_family(vix_quote: dict[str, Any]) -> dict[str, Any]:
    """India VIX regime/context family.

    VIX is not intrinsically bullish or bearish. This family therefore does
    not cast CE/PE votes from the VIX level alone; it reports volatility regime
    and change for downstream risk/execution logic.
    """
    ltp=vix_quote.get("ltp"); prev=vix_quote.get("prev_close")
    if not isinstance(ltp,(int,float)) or not isinstance(prev,(int,float)) or prev<=0:
        return {"state":"UNAVAILABLE","ce":0.0,"pe":0.0,
                "quality":{"usable":False},"reasons":["India VIX quote unavailable"]}
    change=(ltp-prev)/prev*100
    if abs(change) < .001 and vix_quote.get("non_moving"):
        return {"state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
                "metrics":{"vix":round(ltp,3),"change_pct":round(change,3)},
                "quality":{"freshness":"NON_MOVING_SNAPSHOT"},
                "reasons":["India VIX snapshot not proven live"]}
    if ltp < 12: regime="LOW"
    elif ltp < 16: regime="NORMAL"
    elif ltp < 22: regime="ELEVATED"
    else: regime="HIGH"
    impulse="EXPANDING" if change>=5 else "COMPRESSING" if change<=-5 else "STABLE"
    return {"state":"NEUTRAL","ce":0.0,"pe":0.0,
            "metrics":{"vix":round(ltp,3),"change_pct":round(change,3),
                       "regime":regime,"impulse":impulse},
            "quality":{"usable":True},
            "reasons":[f"India VIX {regime.lower()} regime; volatility {impulse.lower()}"]}
