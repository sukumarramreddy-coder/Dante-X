from __future__ import annotations
from typing import Any


def _contract_quality(leg: dict[str, Any]) -> float:
    """Execution/Greek quality only; never interpreted as directional probability."""
    q = float((leg.get("quality") or {}).get("execution_score", 0))
    delta = abs(float(leg.get("delta") or 0))
    theta = abs(float(leg.get("theta") or 0))
    delta_fit = max(0.0, 100.0 - abs(delta - 0.50) * 200.0)
    theta_penalty = min(theta, 100.0)
    return round(0.65 * q + 0.25 * delta_fit + 0.10 * (100.0 - theta_penalty), 1)


def shadow_decision(families: dict[str, Any], readiness: dict[str, Any], nifty: dict[str, Any]) -> dict[str, Any]:
    """Translate evidence into an auditable SHADOW plan; never places orders."""
    state = families.get("state", "NO_EDGE")
    if not readiness.get("live_evidence_ready"):
        return {"status": "NO_SETUP", "authorization": "NONE", "reason": "required live evidence not fresh"}
    if state not in {"CE_EVIDENCE", "PE_EVIDENCE"}:
        return {"status": "NO_SETUP", "authorization": "NONE", "reason": f"family consensus {state}"}
    side = "CE" if state == "CE_EVIDENCE" else "PE"
    rows = nifty.get("strikes") or []
    candidates = []
    for r in rows:
        leg = r.get("call" if side == "CE" else "put") or {}
        q = leg.get("quality") or {}
        spread = leg.get("spread_pct")
        if leg.get("ltp") and q.get("execution_score", 0) >= 50 and spread is not None and spread <= 2:
            candidates.append((_contract_quality(leg), -spread, r.get("strike"), leg))
    if not candidates:
        return {"status": "NO_SETUP", "authorization": "NONE", "direction": side, "reason": "no executable option contract"}
    contract_quality, _, strike, leg = max(candidates)
    premium = float(leg["ltp"])
    # Shadow-only premium geometry. Structural underlying invalidation remains required before real authorization.
    stop = round(premium * .85, 2)
    t1 = round(premium * 1.20, 2)
    t2 = round(premium * 1.35, 2)
    risk = round(premium - stop, 2)
    rr = round((t1 - premium) / risk, 2) if risk > 0 else None
    trade_quality = round(0.65 * contract_quality + 0.35 * min((rr or 0) / 2.0 * 100, 100), 1)
    return {
        "status": "DETECTED",
        "authorization": "SHADOW_ONLY",
        "direction": side,
        "contract": {"strike": strike, "expiry": nifty.get("expiry"), "instrument_key": leg.get("instrument_key")},
        "contract_quality": contract_quality,
        "trade_quality": trade_quality,
        "reference_entry": round(premium, 2),
        "reference_stop": stop,
        "reference_t1": t1,
        "reference_t2": t2,
        "reference_rr_t1": rr,
        "probability": None,
        "note": "Trade/contract quality is separate from direction. Probability remains unavailable until calibrated; ARMED requires structural trigger, sizing, costs and validation.",
    }
