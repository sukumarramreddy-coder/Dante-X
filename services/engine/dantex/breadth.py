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
