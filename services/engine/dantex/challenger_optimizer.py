"""Bounded offline portfolio benchmark / validator for quantum-inspired proposals.

No quantum advantage is claimed. An external solver may propose IDs; this module
independently verifies budget and exposure constraints. No broker interface.
"""
from itertools import combinations

from .probability import finite_number


def review_selection(candidates: list[dict], budget: float, proposed_ids: list[str] | None = None) -> dict:
    if len(candidates) > 16 or not finite_number(budget) or budget <= 0:
        raise ValueError("positive budget and at most 16 candidates required")
    ids = set()
    for c in candidates:
        if (not c.get("id") or c["id"] in ids or not c.get("exposure_group")
                or not all(finite_number(c.get(k)) for k in ("risk", "reward", "cost", "probability"))
                or c["risk"] <= 0 or c["reward"] <= 0 or c["cost"] < 0
                or not .20 <= c["probability"] <= .60):
            raise ValueError("invalid or duplicate candidate")
        ids.add(c["id"])

    def valid(rows):
        return (sum(c["risk"] + c["cost"] for c in rows) <= budget
                and len({c["exposure_group"] for c in rows}) == len(rows))

    def objective(rows):
        # Treat every non-target outcome as a full stop, including timeouts.
        return sum(c["probability"] * c["reward"] - (1 - c["probability"]) * c["risk"]
                   - c["cost"] for c in rows)

    if proposed_ids is not None:
        if len(set(proposed_ids)) != len(proposed_ids) or not set(proposed_ids) <= ids:
            raise ValueError("invalid solver proposal")
        selected = [c for c in candidates if c["id"] in proposed_ids]
        if not valid(selected) or objective(selected) < 0:
            raise ValueError("solver proposal violates risk/exposure/objective constraints")
        method = "external_proposal_validation"
    else:
        feasible = (rows for size in range(len(candidates) + 1)
                    for rows in combinations(candidates, size) if valid(rows))
        selected = max(feasible, key=objective)
        method = "exact_small_set_reference"
    return {"selected_ids": [c["id"] for c in selected], "method": method,
            "risk_including_cost": sum(c["risk"] + c["cost"] for c in selected),
            "hypothetical_objective": objective(selected), "authorization": "NONE",
            "mode": "shadow", "auto_execution": False, "calibration_ready": False}
