"""Frozen, review-only priors. These numbers are NOT fitted or calibrated win rates."""
from __future__ import annotations

from math import isfinite
from typing import Any

VERSION = "provisional-v1"
# A fixed allowlist prevents extra/correlated observations increasing confidence.
FAMILIES = ("structure_location", "options_response", "cross_index",
            "momentum_velocity", "breadth", "sector_leadership",
            "volatility", "derivatives_positioning")


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def index_evidence_priors(options: dict, structures: dict, snapshot: dict) -> dict:
    """Display-only local priors. Never used by consensus, learning or authorization."""
    from .evidence_families import options_family, structure_family

    result = {}
    for symbol in ("NIFTY", "BANKNIFTY"):
        option = options.get(symbol) or {}
        index = (snapshot.get("indices") or {}).get(symbol) or {}
        local = {"structure": structure_family(structures.get(symbol)),
                 "option_response": options_family(option)}
        path_state = (option.get("path_response") or {}).get("state")
        if not path_state or path_state in {"UNAVAILABLE", "STALE_CONTEXT", "WARMING_UP"}:
            local["option_response"]["state"] = "UNAVAILABLE"
        states = {name: family["state"] for name, family in local.items()}
        fresh = index.get("fresh") is True
        ce = sum(state == "CE" for state in states.values())
        pe = sum(state == "PE" for state in states.values())
        conflict = "CONFLICT" in states.values() or (ce > 0 and pe > 0)
        blocked = not fresh or conflict
        strength = 0.0 if blocked else (ce-pe) / 2
        p_ce = round(50 + 15*strength, 2)
        result[symbol] = {
            "version": "index-provisional-v1", "scope": symbol,
            "timestamp": snapshot.get("timestamp"),
            "status": "PRIOR_ONLY" if blocked or not (ce or pe) else "PROVISIONAL",
            "directional": {"ce": p_ce, "pe": round(100-p_ce, 2)},
            "fresh_evidence": fresh, "family_states": states,
            "calibrated": False, "calibration_ready": False, "sample_support": 0,
            "authorization": "NONE", "auto_execution": False, "read_only": True,
            "unit": "percent", "mode": "shadow",
            "data_quality": "STALE_OR_MISSING" if not fresh else "CONFLICT" if conflict else "FRESH",
            "blocked_sources": [] if fresh else [symbol + ".freshness"],
            "missing_families": [name for name, state in states.items()
                                 if state in {"UNAVAILABLE", "STALE_CONTEXT"}],
            "data_reasons": [reason for family in local.values() for reason in family.get("reasons", [])],
            "method": "50 + 15 * (local CE families - local PE families) / 2; conflict/stale => 50",
            "limitations": ["Provisional heuristic; not calibrated profit odds or trade authorization",
                            "Uses only this index's structure and option response; two correlated families",
                            "No fitted model, empirical uncertainty interval or verified outcome support"],
        }
    return result


def evidence_prior(families: dict, readiness: dict) -> dict:
    """One bounded vote per known family, shrunk toward an explicit neutral prior."""
    inputs = families.get("families") or {}
    states = {name: (inputs.get(name) or {}).get("state", "UNAVAILABLE")
              for name in FAMILIES}
    fresh = readiness.get("live_evidence_ready") is True
    ce = sum(state == "CE" for state in states.values())
    pe = sum(state == "PE" for state in states.values())
    conflicts = sum(state == "CONFLICT" for state in states.values())
    # A conflict is a veto even when its numeric vote is zero.
    blocked = not fresh or conflicts > 0 or (ce > 0 and pe > 0)
    strength = 0.0 if blocked else (ce - pe) / len(FAMILIES)
    p_ce = round(50 + 15 * strength, 2)
    return {
        "version": VERSION, "status": "PRIOR_ONLY" if blocked or not (ce or pe) else "PROVISIONAL",
        "calibration_ready": False, "calibrated": False, "sample_support": 0,
        "mode": "shadow", "read_only": True, "auto_execution": False,
        "authorization": "NONE", "unit": "percent", "family_states": states,
        "fresh_evidence": fresh, "evidence_strength": round(abs(strength), 4),
        "coverage": round(sum(s in {"CE", "PE", "NEUTRAL", "CONFLICT"}
                              for s in states.values()) / len(FAMILIES), 4),
        "data_quality": "FRESH" if fresh else "STALE_OR_MISSING",
        "blocked_sources": readiness.get("blocked_sources") or [],
        "data_reasons": [f"{name}: {reason}" for name, family in inputs.items()
                         for reason in (family.get("reasons") or [])
                         if family.get("state") in {"UNAVAILABLE", "STALE_CONTEXT", "CONFLICT"}],
        "missing_families": [name for name, state in states.items()
                             if state in {"UNAVAILABLE", "STALE_CONTEXT"}],
        "directional": {"ce": p_ce, "pe": round(100 - p_ce, 2),
                        "meaning": "heuristic relative directional preference; not option profit odds"},
        "regime": {"status": "UNAVAILABLE", "confidence": None},
        "method": "50 + 15 * (CE families - PE families) / 8; conflicts/stale reset to 50",
        "limitations": ["No fitted model or validated samples", "Families may remain correlated",
                        "No empirical uncertainty interval", "Not trade authorization"],
    }


def review_probability(families: dict, readiness: dict, decision: dict) -> dict:
    result = evidence_prior(families, readiness)
    result["target_before_stop"] = None
    result["target_status"] = "UNAVAILABLE_NO_ELIGIBLE_SETUP"
    entry, stop, target = (decision.get(k) for k in
                           ("reference_entry", "reference_stop", "reference_t1"))
    contract = decision.get("contract") or {}
    if (decision.get("status") != "DETECTED" or not result["fresh_evidence"]
            or not contract.get("instrument_key") or not contract.get("expiry")
            or not all(finite_number(x) for x in (entry, stop, target))
            or not 0 < stop < entry < target):
        return result
    # Driftless barrier-distance prior, discounted 20% for timeout/unknown dynamics.
    # This is a deliberately frozen engineering heuristic, not a pricing model.
    prior = (entry - stop) / (target - stop)
    signed = (result["directional"]["ce"] - 50) / 15
    alignment = signed if decision.get("direction") == "CE" else -signed
    estimate = round(100 * min(.60, max(.20, .8 * prior + .10 * alignment)), 2)
    result.update(target_status="PROVISIONAL", target_before_stop={
        "probability": estimate, "event": "T1 before stop within 30 minutes or session close",
        "horizon_minutes": 30, "entry": entry, "stop": stop, "target": target,
        "contract": contract, "barrier_prior": round(prior, 6),
        "method": "clip(0.8 * (entry-stop)/(target-stop) + 0.10 * signed_family_strength, 0.20, 0.60)",
        "complement": "stop OR timeout without T1; not P(stop before T1)",
        "costs_included": False, "fill_assumed": False,
        "limitations": "Reference premium barriers only; no slippage, fees, IV/theta model or calibrated horizon dynamics",
    })
    return result
