from dataclasses import replace
from datetime import datetime, timedelta, timezone
from math import log

import pytest

from dantex.challengers import Provenance, hmm_filter, predict_challenger, probability_metrics
from dantex.challenger_optimizer import review_selection
from dantex.meta_labels import triple_barrier

AT = datetime(2026, 9, 29, 5, 0, tzinfo=timezone.utc)
PROVENANCE = Provenance("model", "v1", "a" * 64, AT - timedelta(days=1), ("x",), 100,
                        "T1_BEFORE_STOP_30M_SESSION")


class Estimator:
    classes_ = (0, 1)

    def predict_proba(self, features):
        assert features == [[1.0]]
        return [[.01, .99]]


@pytest.mark.parametrize("kind", ["lightgbm", "xgboost", "qlib", "triple_barrier_meta"])
def test_adapter_provenance_shrinkage_and_zero_weight(kind):
    r = predict_challenger(kind, Estimator(), PROVENANCE, {"x": 1.0},
                           features_available_at=AT, as_of=AT)
    assert r["raw_probability"] == .99 and r["review_probability"] == .60
    assert r["weight"] == 0 and r["authorization"] == "NONE"
    assert r["calibration_ready"] is False and r["artifact_sha256"] == "a" * 64


@pytest.mark.parametrize("change", [
    {"training_labels_available_at": AT}, {"training_labels_available_at": AT.replace(tzinfo=None)},
    {"artifact_sha256": "unverified"}, {"sample_support": 0}, {"features": ("x", "x")},
    {"target_event": "DIRECTION_UP"},
])
def test_invalid_or_leaky_artifacts_rejected(change):
    with pytest.raises(ValueError):
        predict_challenger("lightgbm", Estimator(), replace(PROVENANCE, **change), {"x": 1.0},
                           features_available_at=AT, as_of=AT)


@pytest.mark.parametrize("features,available", [({"x": float("nan")}, AT), ({}, AT),
    ({"x": 1.0}, AT + timedelta(seconds=1)), ({"x": 1.0}, AT.replace(tzinfo=None))])
def test_future_or_invalid_features_rejected(features, available):
    with pytest.raises(ValueError):
        predict_challenger("xgboost", Estimator(), PROVENANCE, features,
                           features_available_at=available, as_of=AT)


@pytest.mark.parametrize("prediction", [[[float("nan"), .5]], [[.2, .9]], [[2, -1]], [[.5]], []])
def test_bad_model_output_rejected(prediction):
    model = Estimator()
    model.predict_proba = lambda _: prediction
    with pytest.raises(ValueError):
        predict_challenger("xgboost", model, PROVENANCE, {"x": 1.0}, features_available_at=AT, as_of=AT)


def test_hmm_is_causal_forward_update_and_rejects_degenerate_values():
    assert hmm_filter([.5, .5], [[.9, .1], [.1, .9]], [.8, .2]) == pytest.approx([.8, .2])
    for emission in ([0, 0], [float("nan"), 1], [-1, 2]):
        with pytest.raises(ValueError):
            hmm_filter([.5, .5], [[.9, .1], [.1, .9]], emission)
    with pytest.raises(ValueError):
        hmm_filter([1, 1], [[.9, .1], [.1, .9]], [.8, .2])


def evaluation_rows():
    return [{"id": str(i), "probability": .5, "outcome": bool(i), "as_of": AT,
             "trained_through": AT - timedelta(days=1), "label_available_at": AT + timedelta(minutes=30)}
            for i in range(2)]


def test_metrics_known_answers_and_leakage_or_duplicates_rejected():
    rows = evaluation_rows()
    result = probability_metrics(rows)
    assert result["brier"] == .25 and result["log_loss"] == pytest.approx(log(2))
    assert result["reliability"][5]["observed_rate"] == .5
    assert result["calibration_ready"] is False
    assert probability_metrics([])["status"] == "NO_SAMPLES"
    with pytest.raises(ValueError):
        probability_metrics(rows + rows)
    rows[0]["trained_through"] = AT
    with pytest.raises(ValueError):
        probability_metrics(rows)


def label(bars, at=AT, evaluated=None):
    return triple_barrier(contract="option1", as_of=at, entry=100, stop=85, target=120,
                          bars=bars, evaluated_at=evaluated or at + timedelta(minutes=30))


def bars(n=30, at=AT):
    return [{"at": at + timedelta(minutes=i), "contract": "option1", "low": 95, "high": 105}
            for i in range(n)]


def test_triple_barriers_target_stop_timeout_and_ambiguity():
    source = bars()
    assert label(source)["status"] == "TIMEOUT" and label(source)["outcome"] is False
    source[2]["high"] = 120
    assert label(source)["status"] == "TARGET" and label(source)["outcome"] is True
    source[1]["low"] = 85
    assert label(source)["status"] == "STOP"
    source[1]["high"] = 120
    assert label(source)["status"] == "CENSORED" and label(source)["outcome"] is None


def test_labels_reject_gaps_identity_mismatch_future_and_censor_at_session_close():
    assert label(bars()[1:])["status"] == "CENSORED"
    source = bars()
    source[0]["contract"] = "other_expiry"
    assert label(source)["status"] == "CENSORED"
    assert label(bars(), evaluated=AT)["status"] == "CENSORED"
    late = AT.replace(hour=9, minute=55)  # 15:25 IST
    assert label(bars(5, late), at=late)["status"] == "TIMEOUT"
    assert label(bars(4, late), at=late)["status"] == "CENSORED"


def candidates():
    return [{"id": str(i), "exposure_group": "NIFTY" if i < 2 else "BANKNIFTY",
             "risk": 100, "reward": 200, "cost": 5, "probability": .5} for i in range(3)]


def test_optimizer_keeps_budget_correlated_exposure_and_authorization_closed():
    r = review_selection(candidates(), 210)
    assert len(r["selected_ids"]) == 2 and r["risk_including_cost"] == 210
    assert r["authorization"] == "NONE" and r["auto_execution"] is False
    assert review_selection(candidates(), 104)["selected_ids"] == []
    for ids in (["0", "1"], ["0", "0"], ["unknown"]):
        with pytest.raises(ValueError):
            review_selection(candidates(), 1000, ids)
    with pytest.raises(ValueError):
        review_selection(candidates(), 100, ["0"])
    assert review_selection(candidates(), 105, ["0"])["method"] == "external_proposal_validation"
    bad = candidates()
    bad[0]["probability"] = .99
    with pytest.raises(ValueError):
        review_selection(bad, 1000)
