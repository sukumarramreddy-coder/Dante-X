from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dantex.freshness import IST
from dantex.outcome_tracker import OutcomeTracker
from dantex.probability import index_evidence_priors
from dantex.validation_recorder import ValidationRecorder


def test_per_index_priors_diverge_without_sharing_votes():
    options = {s: {"path_response": {"state": state}} for s, state in
               [("NIFTY", "CE_STRENGTHENING"), ("BANKNIFTY", "PE_STRENGTHENING")]}
    structures = {s: {"status": "OK", "evidence_eligible": True, "trend": trend} for s, trend in
                  [("NIFTY", "BULLISH"), ("BANKNIFTY", "BEARISH")]}
    snapshot = {"indices": {s: {"fresh": True} for s in options}, "timestamp": datetime.now(IST).isoformat()}
    result = index_evidence_priors(options, structures, snapshot)
    assert result["NIFTY"]["directional"] == {"ce": 65.0, "pe": 35.0}
    assert result["BANKNIFTY"]["directional"] == {"ce": 35.0, "pe": 65.0}
    for value in result.values():
        assert value["authorization"] == "NONE"
        assert value["calibrated"] is value["auto_execution"] is False
    snapshot["indices"]["BANKNIFTY"]["fresh"] = False
    stale = index_evidence_priors(options, structures, snapshot)
    assert stale["NIFTY"] == result["NIFTY"]
    assert stale["BANKNIFTY"]["directional"] == {"ce": 50.0, "pe": 50.0}
    assert stale["BANKNIFTY"]["status"] == "PRIOR_ONLY"
    structures["NIFTY"]["opening_range_state"] = "BELOW_OPENING_RANGE"
    assert index_evidence_priors(options, structures, snapshot)["NIFTY"]["status"] == "PRIOR_ONLY"


def test_missing_local_inputs_are_explicit_neutral_context():
    result = index_evidence_priors({}, {}, {})
    for symbol, review in result.items():
        assert review["scope"] == symbol
        assert review["status"] == "PRIOR_ONLY"
        assert review["missing_families"] == ["structure", "option_response"]
        assert not review["fresh_evidence"]


def test_build_duel_preserves_supplied_quotes(monkeypatch):
    from dantex import api
    quotes = {"NIFTY": {"status": "OK", "id": 1}, "BANKNIFTY": {"status": "OK", "id": 2}}
    monkeypatch.setattr(api.instrument_master, "refresh_async", lambda: None)
    monkeypatch.setattr(api.options_intelligence, "snapshot", Mock(side_effect=AssertionError("refetch")))
    evaluator = Mock(return_value={"decision": {"status": "NO_SETUP"}})
    monkeypatch.setattr(api, "evaluate_option_duel", evaluator)
    api.build_option_duel(quotes)
    evaluator.assert_called_once_with(quotes["NIFTY"], quotes["BANKNIFTY"])


def test_learning_reuses_cycle_payload_without_evaluating_again(monkeypatch):
    from dantex import api
    payload = {"decision": {"status": "NO_SETUP"}}
    monkeypatch.setattr(api, "market_session", lambda now: {"market_open": True})
    monkeypatch.setattr(api, "learning_window", lambda: object())
    monkeypatch.setattr(api, "build_option_duel", Mock(side_effect=AssertionError("second evaluation")))
    monkeypatch.setattr(api.UpstoxCredentials, "from_env", lambda: SimpleNamespace(analytics_token="test"))
    monkeypatch.setattr(api, "UpstoxRestClient", lambda config: None)
    collect = Mock(return_value={})
    monkeypatch.setattr(api, "collect_learning", collect)
    api.run_learning_cycle({}, evaluated_payload=payload)
    assert collect.call_args.args[0] is payload["decision"]


def test_observer_passes_exact_evaluation_into_learning(monkeypatch):
    from dantex import api, observation_loop as module
    class StopLoop(BaseException):
        pass
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 5, 10, 0, tzinfo=IST)
    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(module, "sleep", Mock(side_effect=StopLoop))
    monkeypatch.setattr(module.instrument_master, "refresh_async", lambda: None)
    monkeypatch.setattr(module.options_intelligence, "snapshot", lambda symbol: {"status": "OK", "symbol": symbol})
    monkeypatch.setattr(module.validation_recorder, "record_duel", Mock())
    evaluator = Mock(return_value={"decision": {"status": "NO_SETUP"}})
    learner = Mock()
    monkeypatch.setattr(api, "evaluate_option_duel", evaluator)
    monkeypatch.setattr(api, "run_learning_cycle", learner)
    loop = module.ObservationLoop(_outcomes=SimpleNamespace(observe=Mock()))
    with pytest.raises(StopLoop):
        loop._run()
    assert loop.samples == 1
    evaluator.assert_called_once()
    learner.assert_called_once()
    assert learner.call_args.kwargs["evaluated_payload"] is evaluator.return_value


def test_eligible_query_filters_before_limit_and_preserves_history(tmp_path):
    recorder = ValidationRecorder(str(tmp_path / "validation.db"))
    for _ in range(205):
        recorder.record_duel({"state": "OBSERVATION"}, {"status": "MARKET_OBSERVATION"})
    rid = recorder.record_duel({"state": "CE_EVIDENCE"}, {"status": "DETECTED"})
    assert [row["id"] for row in recorder.unlabelled(1)] == [rid]
    tracker = OutcomeTracker(recorder, started_at=datetime.now(IST)+timedelta(seconds=1))
    assert tracker.observe({}, now=datetime.now(IST)+timedelta(hours=1)) == 0
    assert recorder.unlabelled(1)[0]["id"] == rid


def tracker_fixture():
    started = (datetime.now(IST)-timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    sample = {"id": 1, "recorded_at": started.isoformat(), "decision": {
        "status": "DETECTED", "contract": {"instrument_key": "option"},
        "entry": 100, "stop": 90, "t1": 110, "t2": 120}}
    labels = []
    recorder = SimpleNamespace(unlabelled=lambda limit, **kwargs: [] if labels else [sample],
                               label=lambda *args: labels.append(args))
    return started, OutcomeTracker(recorder, horizon_minutes=1, started_at=started), labels


def quote(at, price=111):
    return {"NIFTY": {"evidence_eligible": True, "strikes": [{"call": {
        "instrument_key": "option", "ltp": price, "price_timestamp": at.isoformat()}}]}}


def test_forward_prices_are_bounded_to_horizon_and_paths_released():
    started, tracker, labels = tracker_fixture()
    tracker.observe(quote(started+timedelta(seconds=30)), now=started+timedelta(seconds=30))
    tracker.observe(quote(started+timedelta(minutes=2), 80), now=started+timedelta(minutes=2))
    assert labels[0][1]["eligible"] is True
    assert labels[0][1]["first_event"] == "T1"
    assert labels[0][1]["observations"] == 1  # price after deadline was not used
    assert tracker.paths == {}


def test_missing_future_and_stale_prices_are_censored_not_wins():
    started, tracker, labels = tracker_fixture()
    tracker.observe(quote(started+timedelta(hours=1)), now=started+timedelta(seconds=30))
    assert tracker.paths == {}
    tracker.observe({}, now=started+timedelta(minutes=2))
    assert labels[0][1]["eligible"] is False
    assert labels[0][1]["status"] == "CENSORED"


def test_large_gap_is_censored():
    started, tracker, labels = tracker_fixture()
    tracker.horizon = timedelta(minutes=30)
    tracker.observe(quote(started+timedelta(seconds=30)), now=started+timedelta(seconds=30))
    tracker.observe(quote(started+timedelta(minutes=30)), now=started+timedelta(minutes=30))
    assert labels[0][1]["status"] == "CENSORED"


def test_unverified_quotes_never_enter_forward_path():
    started, tracker, labels = tracker_fixture()
    payload = quote(started+timedelta(seconds=30))
    payload["NIFTY"]["evidence_eligible"] = False
    tracker.observe(payload, now=started+timedelta(seconds=30))
    assert tracker.paths == {}
    assert not labels
    tracker.observe({}, now=started+timedelta(minutes=2))
    assert labels[0][1]["status"] == "CENSORED"
