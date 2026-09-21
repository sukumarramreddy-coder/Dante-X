from __future__ import annotations

from typing import Any


def _path_vote(path: dict[str, Any]) -> tuple[int, int, str]:
    state = path.get("state")
    if state == "CE_STRENGTHENING":
        return 3, 0, "ATM CE/PE path confirms upside"
    if state == "PE_STRENGTHENING":
        return 0, 3, "ATM CE/PE path confirms downside"
    if state == "BULL_MOVE_REFUSED_BY_OPTIONS":
        return 0, 2, "Options refuse underlying upside"
    if state == "BEAR_MOVE_REFUSED_BY_OPTIONS":
        return 2, 0, "Options refuse underlying downside"
    return 0, 0, f"Option path {state or 'unavailable'}"


def _structure_vote(structure: dict[str, Any]) -> tuple[int, int, list[str]]:
    """Price structure is the primary evidence family; conflicts remain explicit."""
    ce = pe = 0
    reasons: list[str] = []
    trend = structure.get("trend")
    opening = structure.get("opening_range_state")
    location = structure.get("location") or {}

    if trend == "BULLISH":
        ce += 3
        reasons.append("bullish EMA structure")
    elif trend == "BEARISH":
        pe += 3
        reasons.append("bearish EMA structure")

    if opening == "ABOVE_OPENING_RANGE":
        ce += 2
        reasons.append("price above opening-range high")
    elif opening == "BELOW_OPENING_RANGE":
        pe += 2
        reasons.append("price below opening-range low")

    if location.get("vs_prior_high") == "ABOVE":
        ce += 2
        reasons.append("price above prior-day high")
    if location.get("vs_prior_low") == "BELOW":
        pe += 2
        reasons.append("price below prior-day low")
    if location.get("vs_vwap") == "ABOVE":
        ce += 1
        reasons.append("price above VWAP")
    elif location.get("vs_vwap") == "BELOW":
        pe += 1
        reasons.append("price below VWAP")
    return ce, pe, reasons


def duel(nifty: dict[str, Any], bank: dict[str, Any], nifty_structure: dict[str, Any] | None = None, bank_structure: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evidence duel only. It cannot authorize a trade."""
    ce = pe = 0
    evidence: list[str] = []
    structure_conflict = False
    for label, structure in (("NIFTY", nifty_structure), ("BANKNIFTY", bank_structure)):
        if not structure or structure.get("status") != "OK":
            evidence.append(f"{label} structure unavailable")
            continue
        sc, sp, reasons = _structure_vote(structure)
        ce += sc
        pe += sp
        if sc and sp:
            structure_conflict = True
        evidence.extend(f"{label} structure: {reason}" for reason in reasons)
    for label, snap in (("NIFTY", nifty), ("BANKNIFTY", bank)):
        c, p, reason = _path_vote(snap.get("path_response") or {})
        ce += c
        pe += p
        evidence.append(f"{label}: {reason}")

    nspot, bspot = nifty.get("spot"), bank.get("spot")
    npath = (nifty.get("path_response") or {}).get("spot_change")
    bpath = (bank.get("path_response") or {}).get("spot_change")
    if npath is not None and bpath is not None:
        if npath > 0 and bpath > 0:
            ce += 2
            evidence.append("Cross-index confirmation: both underlying paths up")
        elif npath < 0 and bpath < 0:
            pe += 2
            evidence.append("Cross-index confirmation: both underlying paths down")
        elif npath != 0 and bpath != 0:
            evidence.append("Cross-index divergence")

    state = "NO_EDGE"
    if ce >= 4 and ce >= pe + 3:
        state = "CE_EVIDENCE"
    elif pe >= 4 and pe >= ce + 3:
        state = "PE_EVIDENCE"
    elif ce and pe:
        state = "CONFLICT"

    if structure_conflict and state in {"CE_EVIDENCE", "PE_EVIDENCE"}:
        state = "CONFLICT"

    return {
        "state": state,
        "ce_evidence_score": ce,
        "pe_evidence_score": pe,
        "evidence": evidence,
        "inputs": {"nifty_spot": nspot, "banknifty_spot": bspot},
        "structure_conflict": structure_conflict,
        "authorization": "NONE",
        "note": "Heuristic evidence score, not calibrated probability and not an ARMED/GO trade signal.",
    }
