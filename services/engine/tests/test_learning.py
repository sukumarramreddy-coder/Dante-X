from copy import deepcopy
from datetime import datetime, timedelta
import json

import pytest

from dantex.decision import shadow_decision
from dantex.learning import IST, LearningWindow
from dantex.learning_runtime import collect_learning
from dantex.probability import FAMILIES


def decision():
    return shadow_decision({"state": "CE_EVIDENCE", "families": {k: {"state": "CE"} for k in FAMILIES}},
        {"live_evidence_ready": True}, {"expiry": "2026-12-31", "strikes": [{"strike": 25000, "call": {
            "instrument_key": "NSE_FO|test", "ltp": 100, "delta": .5, "theta": -1,
            "spread_pct": .5, "quality": {"execution_score": 90}}}]})


def dates(n):
    day = datetime(2026, 5, 4, 9, 20, tzinfo=IST)
    output = []
    while len(output) < n:
        if day.weekday() < 5:
            output.append(day)
        day += timedelta(days=1)
    return output


def observed_bars(at, hit):
    return [{"at": at + timedelta(minutes=i), "contract": "NSE_FO|test",
             "low": 99 if hit else 80, "high": 125 if hit else 105} for i in range(30)]


def simulate(window, days, *, wins=7):
    frozen = None
    for day in days:
        for i in range(10):
            now = day + timedelta(minutes=31*i)
            rid = window.admit(decision(), now=now)
            assert rid is not None
            at = now + timedelta(minutes=1)
            window.resolve(rid, observed_bars(at, i < wins), now=at + timedelta(minutes=30))
        report = window.report(day + timedelta(hours=7))
        if report["model_sha256"]:
            if frozen:
                assert report["model_sha256"] == frozen
            frozen = report["model_sha256"]


def test_thirty_sessions_freeze_validate_and_publish_manual_only(tmp_path):
    path = tmp_path / "learning.sqlite3"
    window = LearningWindow(path, durable=True)
    days = dates(31)
    simulate(window, days[:20])
    trained = window.report(days[20])
    assert trained["completed_sessions"] == 20 and trained["state"] == "VALIDATING"
    assert trained["calibration_ready"] is False
    frozen = trained["model_sha256"]
    # Reopening from disk must preserve the training cutoff and exact model.
    window = LearningWindow(path, durable=True)
    simulate(window, days[20:30])
    report = window.report(days[30])
    assert report["completed_sessions"] == 30 and report["calibration_ready"] is True
    assert report["model_sha256"] == frozen
    assert report["training_samples"] == 200 and report["validation_samples"] == 100
    assert report["metrics"]["brier"] < report["metrics"]["baseline_brier"]
    assert report["metrics"]["calibration_error"] == pytest.approx(.05)
    manual = window.publish(decision(), now=days[30])
    assert manual["status"] == "VALIDATED_SIGNAL"
    assert manual["calibrated_probability"] == 65
    assert manual["authorization"] == "MANUAL_REVIEW_ONLY"
    assert manual["auto_execution"] is False and manual["live_orders"] is False
    assert manual["decision"]["authorization"] == "SHADOW_ONLY"
    assert manual["decision"]["calibration_ready"] is False  # provisional estimate is still provisional
    assert window.admit(decision(), now=days[30]) is None
    stale = deepcopy(decision())
    stale["probability_review"]["fresh_evidence"] = False
    assert window.publish(stale, now=days[30])["status"] == "WAIT"
    unsupported = deepcopy(decision())
    unsupported["direction"] = "PE"
    assert window.publish(unsupported, now=days[30])["status"] == "WAIT"
    assert not window.report(days[30] + timedelta(days=31))["calibration_ready"]
    json.dumps(report, allow_nan=False)


def test_thirty_sessions_with_bad_holdout_never_go_live_or_refit(tmp_path):
    window = LearningWindow(tmp_path / "failed.sqlite3", durable=True)
    days = dates(31)
    simulate(window, days[:20])
    frozen = window.report(days[20])["model_sha256"]
    simulate(window, days[20:30], wins=1)
    result = window.report(days[30])
    assert result["state"] == "VALIDATION_FAILED" and not result["calibration_ready"]
    assert result["model_sha256"] == frozen
    assert any("lower bound" in reason for reason in result["blockers"])
    assert window.publish(decision(), now=days[30])["status"] == "WAIT"
    assert window.admit(decision(), now=days[30]) is None


def test_calendar_days_partial_sessions_duplicate_and_ambiguous_outcomes_do_not_advance(tmp_path):
    window = LearningWindow(tmp_path / "partial.sqlite3", durable=True)
    now = dates(1)[0]
    assert window.report(now + timedelta(days=100))["completed_sessions"] == 0
    rid = window.admit(decision(), now=now)
    assert window.admit(decision(), now=now) is None
    at = now + timedelta(minutes=1)
    bars = observed_bars(at, True)
    bars[0]["low"] = 80
    assert not window.resolve(rid, bars, now=now + timedelta(minutes=10))
    assert window.resolve(rid, bars, now=at + timedelta(minutes=30))
    assert not window.resolve(rid, observed_bars(at, True), now=at + timedelta(minutes=31))
    report = window.report(now + timedelta(days=1))
    assert report["censored_samples"] == 1 and report["completed_sessions"] == 0


def test_unverified_durability_blocks_otherwise_passing_window(tmp_path):
    window = LearningWindow(tmp_path / "ephemeral.sqlite3", durable=False)
    days = dates(31)
    simulate(window, days[:30])
    report = window.report(days[30])
    assert report["completed_sessions"] == 30
    assert not report["calibration_ready"]
    assert "learning store is not verified durable" in report["blockers"]


def test_invalid_stale_and_end_of_session_decisions_never_admitted(tmp_path):
    window = LearningWindow(tmp_path / "invalid.sqlite3")
    now = dates(1)[0]
    d = decision()
    d["probability_review"]["fresh_evidence"] = False
    assert window.admit(d, now=now) is None
    assert window.admit(decision(), now=now.replace(hour=15, minute=15)) is None
    with pytest.raises(ValueError):
        window.admit(decision(), now=now.replace(tzinfo=None))


def test_background_reads_only_contract_future_candles_and_preserves_evidence(tmp_path):
    window = LearningWindow(tmp_path / "runtime.sqlite3")
    now = dates(1)[0]
    at = now + timedelta(minutes=1)
    class Client:
        def intraday_candles(self, key, *, unit, interval):
            assert key == "NSE_FO|test" and unit == "minutes" and interval == 1
            rows = [[b["at"].isoformat(), 100, b["high"], b["low"], 105, 100]
                    for b in observed_bars(at, True)]
            return {"data": {"candles": rows[::-1]}}
    collect_learning(decision(), Client(), now=now, window=window)
    report = collect_learning({}, Client(), now=at + timedelta(minutes=31), window=window)
    assert report["pending_samples"] == 0
    with window.connect() as db:
        result, evidence = db.execute("SELECT result,evidence FROM learning_events").fetchone()
        assert json.loads(result)["status"] == "TARGET"
        assert len(json.loads(evidence)) == 30


def test_temporary_env_path_never_claims_durable(tmp_path, monkeypatch):
    from dantex.learning import learning_from_env
    monkeypatch.setenv("DANTEX_LEARNING_DB", str(tmp_path / "temp.sqlite3"))
    monkeypatch.setenv("DANTEX_LEARNING_DURABLE", "true")
    monkeypatch.setattr("dantex.learning.tempfile.gettempdir", lambda: str(tmp_path))
    assert learning_from_env().durable is False


def test_learning_api_reflects_real_store_and_keeps_manual_signal_closed(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from dantex import api
    window = LearningWindow(tmp_path / "api.sqlite3", durable=True)
    monkeypatch.setattr(api, "learning_window", lambda: window)
    monkeypatch.setattr(api, "build_option_duel", lambda: {"decision": decision()})
    client = TestClient(api.app)
    assert client.get("/v1/calibration/learning").json()["completed_sessions"] == 0
    result = client.get("/v1/signals/manual").json()
    assert result["status"] == "WAIT" and result["auto_execution"] is False
