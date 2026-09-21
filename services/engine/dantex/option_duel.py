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


def duel(nifty: dict[str, Any], bank: dict[str, Any]) -> dict[str, Any]:
    """Evidence duel only. It cannot authorize a trade."""
    ce = pe = 0
    evidence: list[str] = []
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

    return {
        "state": state,
        "ce_evidence_score": ce,
        "pe_evidence_score": pe,
        "evidence": evidence,
        "inputs": {"nifty_spot": nspot, "banknifty_spot": bspot},
        "authorization": "NONE",
        "note": "Heuristic evidence score, not calibrated probability and not an ARMED/GO trade signal.",
    }
