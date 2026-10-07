from copy import deepcopy
from datetime import datetime, timedelta
import json

import pytest
from fastapi.testclient import TestClient

from dantex.expert_engine import four_way, option_quality, position_governor, reassess, reconcile
from dantex.expert_provider import ExpertAdvice, OpenAIExpertReasoningProvider
from dantex.expert_runtime import DecisionRuntime
from dantex.expert_snapshot import normalized_snapshot
from dantex.freshness import IST
from dantex.validation_recorder import ValidationRecorder


@pytest.fixture
def snapshot():
    now = datetime(2026, 9, 29, 10, 30, tzinfo=IST)
    bars = [{"ts": (now-timedelta(minutes=15-i)).isoformat(), "open": 100+i,
             "high": 102+i, "low": 99+i, "close": 101+i} for i in range(15)]
    structure = {"evidence_eligible": True, "last_candle_ts": bars[-1]["ts"],
                 "recent_candles": bars, "trend": "BULLISH", "opening_range_state": "ABOVE_OPENING_RANGE",
                 "vwap": 105, "ema11": 110, "ema46": 105, "ema120": 100, "prior_day": {"close": 100}}
    leg = {"instrument_key": "test-option", "ltp": 20, "bid_price": 19.95, "ask_price": 20.05,
           "spread_pct": .5, "delta": .5, "gamma": .01, "theta": -1, "vega": 2, "iv": 15,
           "volume": 1000000, "oi": 250000, "quality": {"execution_score": 90}}
    option = {"evidence_eligible": True, "derivatives_evidence_eligible": True, "spot": 115,
              "expiry": "2026-10-01", "strikes": [{"strike": 115, "call": leg, "put": {**leg, "delta": -.5}}],
              "path_response": {"last_sample_at": now.isoformat(), "state": "CE_STRENGTHENING"}}
    families = {"freshness": {name: {"eligible": True} for name in ("breadth", "volatility", "sector_leadership")}}
    return normalized_snapshot({s: deepcopy(option) for s in ("NIFTY", "BANKNIFTY")},
                               {s: deepcopy(structure) for s in ("NIFTY", "BANKNIFTY")}, families, now=now)


def advice():
    return {"regime": "TREND_UP", "nifty": {"ce_probability": 70., "pe_probability": 30., "action": "HOLD"},
            "banknifty": {"ce_probability": 65., "pe_probability": 35., "action": "HOLD"},
            "best_candidate": {"instrument": "NONE", "side": "NONE", "strike": None, "expiry": None,
                               "entry_zone": None, "invalidation": None, "target_1": None, "target_2": None, "risk_reward": None},
            "continuation_case": "structure", "reversal_case": "failed high", "opposite_side_trigger": "loss of low",
            "missing_data": [], "confidence_basis": "unvalidated evidence", "calibration_status": "CALIBRATED"}


def response(value=None):
    return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(value or advice())}]}]}


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("DANTEX_OPENAI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("DANTEX_OPENAI_MODEL", "configured-model")


@pytest.mark.parametrize("side,path,expected", [("BEARISH", "BEAR_MOVE_REFUSED_BY_OPTIONS", "CE"),
                                               ("BULLISH", "BULL_MOVE_REFUSED_BY_OPTIONS", "PE")])
def test_opposite_reversal_after_directional_thesis(snapshot, side, path, expected):
    index = snapshot["indices"]["NIFTY"]
    index["structure"]["trend"] = side
    index["path"]["state"] = path
    result = four_way(snapshot)
    assert result["regimes"]["NIFTY"]["reversal"] == expected
    assert any(c["side"] == expected for c in result["reversal_case"])
    assert len(result["candidates"]) == 4


@pytest.mark.parametrize("trend,expected", [("BULLISH", "TREND_UP"), ("BEARISH", "TREND_DOWN"), ("MIXED", "RANGE")])
def test_regimes(snapshot, trend, expected):
    index = snapshot["indices"]["NIFTY"]
    index["structure"]["trend"] = trend
    index["closed_bars"][-1].update(high=115, low=112, close=114)
    assert reassess(index)["regime"] == expected


@pytest.mark.parametrize("field,value,expected", [("high", 130, "failed_breakout"), ("low", 80, "failed_breakdown")])
def test_failed_extensions(snapshot, field, value, expected):
    index = snapshot["indices"]["NIFTY"]
    index["closed_bars"][-1][field] = value
    if field == "high":
        index["closed_bars"][-1]["close"] = 114
    assert reassess(index)[expected]


def test_expiry_stress(snapshot):
    index = snapshot["indices"]["NIFTY"]
    index["expiry_day"] = True
    leg = index["legs"][0]
    leg["theta"] = -10
    assert option_quality(leg, index)["expiry_stress"]


def test_missing_greeks_and_stale_block(snapshot):
    snapshot["indices"]["NIFTY"]["legs"][0]["gamma"] = None
    snapshot["indices"]["BANKNIFTY"]["fresh"] = False
    result = four_way(snapshot)
    assert not any(c["shadow_candidate"] for c in result["candidates"])
    assert all(c["action"] != "GO" for c in result["candidates"])


@pytest.mark.parametrize("failure", [TimeoutError("test-secret"), ValueError("bad json")])
def test_expert_failures_are_redacted(snapshot, enabled, failure):
    def fail(*args):
        raise failure
    result = OpenAIExpertReasoningProvider(transport=fail).evaluate(snapshot)
    assert result["advice"] is None
    assert "test-secret" not in str(result)


def test_invalid_json_and_refusal(snapshot, enabled):
    for value in ({"status": "incomplete"}, {"status": "completed", "output": []}):
        assert OpenAIExpertReasoningProvider(transport=lambda *args, value=value: value).evaluate(snapshot)["advice"] is None


def test_risk_exit_beats_expert_hold(snapshot):
    snapshot["position"] = {"current_premium": 10, "stop": 11, "risk_consumed": 1, "maximum_risk": 10}
    result = reconcile(snapshot, four_way(snapshot), advice())
    assert result["action"] == "EXIT"
    assert not result["auto_execution"]


def test_position_contributes_zero_scoring_bias(snapshot):
    before = four_way(snapshot)
    snapshot["position"] = {"side": "PE", "entry": 100, "qty": 500}
    assert four_way(snapshot) == before


def test_major_impulse_resets_all_four(snapshot):
    snapshot["indices"]["NIFTY"]["closed_bars"][-1].update(close=150, high=151)
    result = four_way(snapshot)
    assert result["four_way_reset"]
    assert len(result["candidates"]) == 4


def test_no_edge_and_checkpoint(snapshot):
    snapshot["session"]["decision_checkpoint_reached"] = True
    for index in snapshot["indices"].values():
        index["structure"] = {"trend": "MIXED"}
        index["path"] = {}
        index["closed_bars"] = []
    assert all(c["action"] == "NO_EDGE" for c in four_way(snapshot)["candidates"])


def test_model_cannot_claim_calibration_and_cache_is_exact(snapshot, enabled):
    calls = []
    def transport(payload, timeout):
        calls.append(payload)
        return response()
    provider = OpenAIExpertReasoningProvider(transport=transport)
    result = provider.evaluate(snapshot)
    assert result["advice"]["calibration_status"] == "UNCALIBRATED"
    assert provider.evaluate(snapshot)["status"] == "CACHED"
    assert len(calls) == 1
    assert "test-secret" not in json.dumps(calls)
    assert calls[0]["text"]["format"]["strict"] is True
    assert "tools" not in calls[0]


def test_rate_limit_and_schema(snapshot, enabled, monkeypatch):
    monkeypatch.setenv("DANTEX_OPENAI_MAX_CALLS_PER_MINUTE", "1")
    provider = OpenAIExpertReasoningProvider(transport=lambda *args: response())
    provider.evaluate(snapshot)
    snapshot["snapshot_id"] = "new"
    snapshot["evaluation_trigger"] = {"impulse": True}
    assert provider.evaluate(snapshot)["status"] == "RATE_LIMITED"
    invalid = advice()
    invalid["nifty"]["ce_probability"] = 101
    with pytest.raises(ValueError):
        ExpertAdvice.model_validate(invalid)


def test_app_endpoints_work_disabled(tmp_path, monkeypatch):
    from dantex import api
    monkeypatch.setenv("DANTEX_OPENAI_ENABLED", "false")
    monkeypatch.delenv("DANTEX_VALIDATION_REST_URL", raising=False)
    monkeypatch.delenv("DANTEX_VALIDATION_REST_KEY", raising=False)
    runtime = DecisionRuntime(ValidationRecorder(str(tmp_path/"audit.db")))
    monkeypatch.setattr(api, "decision_runtime", runtime)
    client = TestClient(api.app)
    assert client.get("/v1/decision/current").json()["final"]["action"] == "NO_EDGE"
    assert client.get("/v1/expert/status").json()["enabled"] is False
    runtime.evaluate({}, {}, {})
    assert len(client.get("/v1/decision/history").json()["evaluations"]) == 1
    assert client.get("/v1/decision/current").json()["final"]["calibrated_probability"] is None


@pytest.mark.parametrize("field", ["market_invalidated", "premium_invalidated"])
def test_independent_invalidations(field):
    position = {"current_premium": 100, "stop": 90, "risk_consumed": 1, "maximum_risk": 10, field: True}
    assert position_governor(position, None)["action"] == "EXIT"
