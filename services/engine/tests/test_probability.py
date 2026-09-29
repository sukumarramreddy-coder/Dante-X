from copy import deepcopy
import json

import pytest

from dantex.decision import shadow_decision
from dantex.probability import FAMILIES, evidence_prior


def setup(side="CE"):
    families = {"state": f"{side}_EVIDENCE", "families": {
        name: {"state": side} for name in FAMILIES}}
    chain = {"expiry": "2026-09-30", "strikes": [{"strike": 25000, "call": {
        "ltp": 100, "spread_pct": 1, "delta": .5, "theta": -2,
        "instrument_key": "CE1", "quality": {"execution_score": 90}}, "put": {
        "ltp": 100, "spread_pct": 1, "delta": -.5, "theta": -2,
        "instrument_key": "PE1", "quality": {"execution_score": 90}}}]}
    return families, {"live_evidence_ready": True}, chain


@pytest.mark.parametrize("side", ["CE", "PE"])
def test_estimates_are_bounded_reviewable_and_do_not_authorize(side):
    args = setup(side)
    before = deepcopy(args)
    d = shadow_decision(*args)
    assert args == before
    assert d["probability"] == 44.29
    assert d["probability_status"] == "PROVISIONAL"
    assert d["authorization"] == "SHADOW_ONLY" and d["status"] == "DETECTED"
    assert d["calibration_ready"] is False and d["auto_execution"] is False
    review = d["probability_review"]
    assert review["directional"][side.lower()] == 65
    assert review["directional"]["ce"] + review["directional"]["pe"] == 100
    assert review["sample_support"] == 0 and review["regime"]["confidence"] is None
    assert review["target_before_stop"]["contract"]["instrument_key"] == f"{side}1"
    assert all(m["weight"] == 0 for m in d["challengers"]["models"])
    json.dumps(d, allow_nan=False)


@pytest.mark.parametrize("ready", [False, None, "true", 1])
def test_stale_or_unproven_inputs_never_emit_setup_probability(ready):
    families, _, chain = setup()
    d = shadow_decision(families, {"live_evidence_ready": ready}, chain)
    assert d["probability"] is None and d["authorization"] == "NONE"
    assert d["probability_review"]["directional"]["ce"] == 50
    assert d["probability_review"]["status"] == "PRIOR_ONLY"


def test_duplicate_unknown_families_and_numeric_scores_cannot_inflate_estimate():
    families, ready, chain = setup()
    original = shadow_decision(families, ready, chain)
    families["families"].update({f"copy{i}": {"state": "CE", "ce": 10000} for i in range(100)})
    families["family_counts"] = {"ce": 100000}
    assert shadow_decision(families, ready, chain)["probability"] == original["probability"]
    for family in FAMILIES:
        families["families"][family] = {"state": "UNAVAILABLE"}
    assert shadow_decision(families, ready, chain)["probability"] < original["probability"]


def test_conflict_even_with_zero_weight_forces_neutral_review():
    families, ready, chain = setup()
    families["state"] = "CONFLICT"
    families["families"]["momentum_velocity"] = {"state": "CONFLICT", "ce": 0, "pe": 0}
    result = shadow_decision(families, ready, chain)
    assert result["authorization"] == "NONE" and result["probability"] is None
    assert result["probability_review"]["directional"]["ce"] == 50


@pytest.mark.parametrize("field,value", [("ltp", float("nan")), ("ltp", float("inf")),
    ("ltp", -1), ("ltp", True), ("spread_pct", -1), ("spread_pct", float("nan")),
    ("delta", float("nan")), ("theta", float("inf")), ("ltp", 1.7e308), ("ltp", .001)])
def test_invalid_contract_never_produces_probability(field, value):
    families, ready, chain = setup()
    chain["strikes"][0]["call"][field] = value
    result = shadow_decision(families, ready, chain)
    assert result["authorization"] == "NONE" and result["probability"] is None
    json.dumps(result, allow_nan=False)


def test_unidentified_contract_cannot_claim_target_probability():
    families, ready, chain = setup()
    chain["strikes"][0]["call"].pop("instrument_key")
    assert shadow_decision(families, ready, chain)["probability"] is None


def test_missing_evidence_is_explicit_neutral_prior_not_fake_sample_support():
    prior = evidence_prior({}, {})
    assert prior["coverage"] == prior["sample_support"] == prior["evidence_strength"] == 0
    assert prior["directional"]["ce"] == 50


def test_recorder_round_trip_preserves_formula_provenance_and_gates(tmp_path):
    from dantex.validation_recorder import ValidationRecorder
    recorder = ValidationRecorder(str(tmp_path / "review.sqlite3"))
    decision = shadow_decision(*setup())
    recorder.record_duel(setup()[0], decision, {})
    assert recorder.recent()[0]["decision"] == decision
    assert recorder.status()["calibration_ready"] is False


def test_read_only_status_endpoint_and_unavailable_data_contract(monkeypatch):
    from fastapi.testclient import TestClient
    from dantex import api
    monkeypatch.setattr(api.instrument_master, "refresh_async", lambda: None)
    monkeypatch.setattr(api.options_intelligence, "snapshot", lambda symbol: {"status": "UNAVAILABLE"})
    client = TestClient(api.app)
    status = client.get("/v1/challengers/status").json()
    assert all(m["status"] == "UNAVAILABLE" for m in status["models"])
    assert status["auto_execution"] is False
    d = client.get("/v1/duel").json()["decision"]
    assert d["authorization"] == "NONE" and d["probability"] is None
    assert d["probability_review"]["directional"]["ce"] == 50
