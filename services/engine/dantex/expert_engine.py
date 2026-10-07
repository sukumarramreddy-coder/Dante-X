"""Independent four-way shadow review. Scores are evidence, never fitted odds."""
from .expert_snapshot import SYMBOLS, number
from .option_duel import _path_vote, _structure_vote


def reassess(index):
    bars = index["closed_bars"]
    if len(bars) < 3:
        return {"regime": "NO_EDGE", "impulse": False, "reversal": None, "rsi": None}
    previous, last = bars[-2:]
    ranges = [b["high"]-b["low"] for b in bars[-15:-1]]
    typical = sum(ranges)/len(ranges)
    impulse = typical > 0 and abs(last["close"]-previous["close"]) >= 1.5*typical
    recent = bars[-15:]
    deltas = [b["close"]-a["close"] for a, b in zip(recent, recent[1:])]
    gains, losses = sum(max(d, 0) for d in deltas), sum(max(-d, 0) for d in deltas)
    rsi = 100*gains/(gains+losses) if gains+losses else 50.0
    high = max(b["high"] for b in bars[-15:-1])
    low = min(b["low"] for b in bars[-15:-1])
    failed_up = last["high"] > high and last["close"] < high
    failed_down = last["low"] < low and last["close"] > low
    path = index["path"].get("state")
    reversal = "PE" if failed_up or path == "BULL_MOVE_REFUSED_BY_OPTIONS" else (
        "CE" if failed_down or path == "BEAR_MOVE_REFUSED_BY_OPTIONS" else None)
    if reversal:
        regime = "REVERSAL_FORMING_UP" if reversal == "CE" else "REVERSAL_FORMING_DOWN"
    elif last["close"] > high:
        regime = "BREAKOUT"
    elif last["close"] < low:
        regime = "BREAKDOWN"
    elif typical and last["high"]-last["low"] < typical*.5:
        regime = "COMPRESSION"
    else:
        regime = {"BULLISH": "TREND_UP", "BEARISH": "TREND_DOWN", "MIXED": "RANGE"}.get(
            index["structure"].get("trend"), "TRANSITION")
    return {"regime": regime, "impulse": impulse, "reversal": reversal,
            "failed_breakout": failed_up, "failed_breakdown": failed_down, "rsi": round(rsi, 2)}


def option_quality(leg, index):
    required = ("ltp", "strike", "delta", "gamma", "theta", "vega", "iv", "spread_pct", "volume", "oi")
    missing = [k for k in required if number(leg.get(k)) is None]
    premium, spot, strike = leg.get("ltp"), index.get("spot"), leg.get("strike")
    if missing or premium <= 0 or spot is None or strike <= 0:
        return {"score": None, "missing_data": missing or ["premium_or_spot"], "premium_value": "UNKNOWN"}
    intrinsic = max(0, spot-strike if leg["side"] == "CE" else strike-spot)
    extrinsic = premium-intrinsic
    delta = abs(leg["delta"])
    expansion = index["path"].get("atm_call_change_pct" if leg["side"] == "CE" else "atm_put_change_pct")
    # Path describes ATM only: do not assign its expansion to wing contracts.
    atm = min((l["strike"] for l in index["legs"] if l.get("strike") is not None), key=lambda s: abs(s-spot))
    expansion = expansion if strike == atm else None
    stress = index["expiry_day"] and abs(leg["theta"])/premium > .15
    invalid = (extrinsic < 0 or not 0 < delta <= 1 or leg["gamma"] < 0
               or leg["iv"] <= 0 or leg["spread_pct"] < 0 or leg["volume"] < 0 or leg["oi"] < 0)
    base = leg.get("execution_score") or 0
    score = max(0, min(100, .65*base + .35*max(0, 100-abs(delta-.5)*200)
                       - (25 if stress else 0) - (25 if expansion is not None and expansion > 50 else 0)))
    return {"score": 0 if invalid else round(score, 2), "intrinsic": intrinsic,
            "extrinsic": extrinsic, "theta_fraction_per_day": abs(leg["theta"])/premium,
            "expiry_stress": stress, "premium_value": "EXTENDED" if expansion is not None and expansion > 50 else "UNKNOWN",
            "premium_expansion_pct": expansion, "gamma": leg["gamma"],
            "move_for_20pct_premium_delta_only": .2*premium/delta if delta else None,
            "missing_data": ["invalid_option_geometry"] if invalid else [],
            "limitations": "Delta-only sensitivity excludes gamma, theta and IV shocks; not a target or valuation."}


def four_way(snapshot):
    candidates, regimes = [], {}
    for symbol in SYMBOLS:
        index = snapshot["indices"][symbol]
        regime = reassess(index)
        regimes[symbol] = regime
        ce, pe, reasons = _structure_vote(index["structure"])
        pc, pp, path_reason = _path_vote(index["path"])
        scores = {"CE": ce+pc, "PE": pe+pp}
        if regime["reversal"]:
            scores[regime["reversal"]] += 4
        for side in ("CE", "PE"):
            legs = [(option_quality(l, index), l) for l in index["legs"] if l["side"] == side]
            quality, leg = max(legs, key=lambda pair: pair[0]["score"] or 0) if legs else ({"score": None}, {})
            other = "PE" if side == "CE" else "CE"
            evidence = scores[side]
            candidate = evidence >= 4 and evidence >= scores[other]+3 and (quality["score"] or 0) >= 50
            missing = [m for m in snapshot["missing_data"] if m.startswith(symbol+".") or m in ("breadth", "volatility", "sector_leadership")]
            # No new probability formula: unsupported directional/continuation odds stay null.
            candidates.append({"instrument": symbol, "side": side, "directional_score": evidence,
                               "directional_evidence": reasons+[path_reason], "option_quality": quality,
                               "contract": {"instrument_key": leg.get("instrument_key"), "strike": leg.get("strike"), "expiry": index["expiry"]},
                               "entry": leg.get("ltp"), "invalidation": None, "target_1": None, "target_2": None,
                               "risk_reward": None, "payoff_asymmetry": None, "entry_quality": "REQUIRES_STRUCTURAL_PLAN",
                               "continuation_probability": None, "reversal_probability": None,
                               "calibrated_probability": None, "calibration_status": "UNCALIBRATED",
                               "opportunity": "REVERSAL" if regime["reversal"] == side else "CONTINUATION",
                               "shadow_candidate": candidate and index["fresh"] and not missing,
                               "action": "WAIT" if candidate and not snapshot["session"]["decision_checkpoint_reached"] else "NO_EDGE",
                               "missing_data": missing+["validated_structural_plan"]})
    ranked = sorted(candidates, key=lambda c: (c["shadow_candidate"], c["directional_score"], c["option_quality"]["score"] or 0), reverse=True)
    return {"candidates": candidates, "regimes": regimes, "best_candidate": ranked[0] if ranked[0]["shadow_candidate"] else None,
            "four_way_reset": any(r["impulse"] for r in regimes.values()),
            "continuation_case": [c for c in candidates if c["opportunity"] == "CONTINUATION"],
            "reversal_case": [c for c in candidates if c["opportunity"] == "REVERSAL"],
            "opposite_side_trigger": "Reassess after failed extension or option refusal; both sides recomputed every cycle."}


def position_governor(position, best):
    if position is None:
        return {"action": "NO_EDGE", "reason": "no position", "would_choose_without_position": None}
    for field in ("current_premium", "stop", "risk_consumed", "maximum_risk"):
        if number(position.get(field)) is None:
            return {"action": "PROTECT", "reason": "MISSING_DATA: position."+field, "would_choose_without_position": False}
    if (position.get("market_invalidated") is True or position.get("premium_invalidated") is True
            or position["current_premium"] <= position["stop"]
            or position["risk_consumed"] >= position["maximum_risk"]):
        return {"action": "EXIT", "reason": "independent market/premium/risk invalidation", "would_choose_without_position": False}
    same = bool(best and best["contract"]["instrument_key"] == position.get("instrument_key"))
    return {"action": "HOLD" if same else "PROTECT", "reason": "fresh unbiased candidate reassessment",
            "would_choose_without_position": same, "averaging_allowed": False}


def reconcile(snapshot, deterministic, expert):
    risk = position_governor(snapshot["position"], deterministic["best_candidate"])
    action = risk["action"] if snapshot["position"] else "NO_EDGE"
    # The new cross-index model has no matching validated calibration artifact.
    # Existing /v1/signals/manual retains its separate, proven publication gate.
    return {"action": action, "risk": risk, "authorization": "SHADOW_ONLY",
            "read_only": True, "auto_execution": False, "calibrated_probability": None,
            "calibration_status": "UNCALIBRATED", "expert_advisory": expert,
            "override_reason": "Risk and deterministic authorization remain authoritative; expert cannot promote action."}
