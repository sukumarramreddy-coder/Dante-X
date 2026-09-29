from __future__ import annotations
from typing import Any
from .probability import finite_number, review_probability
from .challengers import challenger_status


def _contract_quality(leg: dict[str, Any]) -> float:
    """Execution/Greek quality only; never interpreted as directional probability."""
    q = float((leg.get("quality") or {}).get("execution_score", 0))
    delta = abs(float(leg.get("delta") or 0))
    theta = abs(float(leg.get("theta") or 0))
    delta_fit = max(0.0, 100.0 - abs(delta - 0.50) * 200.0)
    theta_penalty = min(theta, 100.0)
    return round(0.65 * q + 0.25 * delta_fit + 0.10 * (100.0 - theta_penalty), 1)


def _shadow_plan(families: dict[str, Any], readiness: dict[str, Any], nifty: dict[str, Any]) -> dict[str, Any]:
    """Translate evidence into an auditable SHADOW plan; never places orders."""
    state = families.get("state", "NO_EDGE")
    if readiness.get("live_evidence_ready") is not True:
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
        if (finite_number(leg.get("ltp")) and leg["ltp"] > 0
                and finite_number(q.get("execution_score")) and 50 <= q["execution_score"] <= 100
                and finite_number(spread) and 0 <= spread <= 2
                and all(finite_number(leg.get(k, 0)) for k in ("delta", "theta"))):
            candidates.append((_contract_quality(leg), -spread, r.get("strike"), leg))
    if not candidates:
        return {"status": "NO_SETUP", "authorization": "NONE", "direction": side, "reason": "no executable option contract"}
    contract_quality, _, strike, leg = max(candidates, key=lambda c: (c[0], c[1]))
    premium = float(leg["ltp"])
    # Shadow-only premium geometry. Structural underlying invalidation remains required before real authorization.
    stop = round(premium * .85, 2)
    t1 = round(premium * 1.20, 2)
    t2 = round(premium * 1.35, 2)
    if (not all(finite_number(x) for x in (stop, t1, t2))
            or not 0 < stop < premium < t1 < t2):
        return {"status": "NO_SETUP", "authorization": "NONE", "direction": side,
                "reason": "invalid reference premium geometry"}
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
        "note": "Trade/contract quality is separate from direction. Provisional probability is review-only; ARMED requires structural trigger, sizing, costs and validation.",
    }


def shadow_decision(families: dict[str, Any], readiness: dict[str, Any], nifty: dict[str, Any]) -> dict[str, Any]:
    """Attach estimates after authorization; neither estimate nor challenger feeds it."""
    decision = _shadow_plan(families, readiness, nifty)
    review = review_probability(families, readiness, decision)
    target = review["target_before_stop"]
    decision.update(probability=target["probability"] if target else None,
                    probability_status=review["target_status"], probability_review=review,
                    calibration_ready=False, mode="shadow", read_only=True,
                    auto_execution=False, challengers=challenger_status())
    return decision
