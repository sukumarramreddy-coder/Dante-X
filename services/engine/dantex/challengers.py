"""Offline challenger boundary. Nothing in this module authorizes or executes trades.

Models are supplied by trusted offline callers; no pickle loading, training,
network calls, automatic promotion or blending into the incumbent decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import log
from typing import Any

from .probability import finite_number

MODEL_KINDS = ("hmm_regime", "lightgbm", "xgboost", "qlib", "triple_barrier_meta",
               "calibration", "quantum_inspired_optimizer")


def challenger_status() -> dict:
    return {"mode": "shadow", "read_only": True, "auto_execution": False,
            "calibration_ready": False, "promotion": "MANUAL_REVIEW_REQUIRED",
            "models": [{"name": name, "status": "UNAVAILABLE",
                        "reason": "No reviewed trained artifact configured", "weight": 0}
                       for name in MODEL_KINDS]}


def aware(at: datetime) -> bool:
    return isinstance(at, datetime) and at.tzinfo is not None and at.utcoffset() is not None


@dataclass(frozen=True)
class Provenance:
    model_id: str
    version: str
    artifact_sha256: str
    training_labels_available_at: datetime
    features: tuple[str, ...]
    sample_support: int
    target_event: str

    def validate(self, as_of: datetime) -> None:
        if (not self.model_id or not self.version or len(self.artifact_sha256) != 64
                or any(c not in "0123456789abcdef" for c in self.artifact_sha256)
                or not aware(as_of) or not aware(self.training_labels_available_at)
                or self.training_labels_available_at >= as_of
                or type(self.sample_support) is not int or self.sample_support <= 0
                or not self.features or len(set(self.features)) != len(self.features)
                or self.target_event != "T1_BEFORE_STOP_30M_SESSION"):
            raise ValueError("invalid provenance or training label leakage")


def predict_challenger(kind: str, estimator: Any, provenance: Provenance,
                       features: dict[str, float], *, features_available_at: datetime,
                       as_of: datetime) -> dict:
    """LightGBM/XGBoost/sklearn-compatible binary meta-label adapter.

    Qlib callers must supply a probability adapter, not raw return scores.
    Every model here must target T1-before-stop at the frozen 30-minute horizon.
    """
    if kind not in {"lightgbm", "xgboost", "qlib", "triple_barrier_meta"}:
        raise ValueError("unsupported probability challenger")
    provenance.validate(as_of)
    if (not aware(features_available_at) or features_available_at > as_of
            or set(features) != set(provenance.features)
            or not all(finite_number(v) for v in features.values())):
        raise ValueError("invalid, missing or future features")
    classes = list(estimator.classes_)
    if classes != [0, 1]:
        raise ValueError("classes must be [0, 1] for the declared binary event")
    prediction = estimator.predict_proba([[features[k] for k in provenance.features]])
    if len(prediction) != 1 or len(prediction[0]) != 2:
        raise ValueError("binary probability shape required")
    probabilities = [float(p) for p in prediction[0]]
    if (not all(finite_number(p) and 0 <= p <= 1 for p in probabilities)
            or abs(sum(probabilities) - 1) > 1e-6):
        raise ValueError("invalid model probabilities")
    raw = probabilities[1]
    return {"kind": kind, "model_id": provenance.model_id, "version": provenance.version,
            "artifact_sha256": provenance.artifact_sha256,
            "training_labels_available_at": provenance.training_labels_available_at.isoformat(),
            "as_of": as_of.isoformat(), "features_available_at": features_available_at.isoformat(),
            "features": dict(features), "sample_support": provenance.sample_support,
            "raw_probability": raw, "review_probability": min(.60, max(.20, .5 + .25 * (raw - .5))),
            "event": "T1_BEFORE_STOP_30M_SESSION", "calibration_ready": False,
            "status": "CHALLENGER_ONLY", "authorization": "NONE", "weight": 0}


def hmm_filter(prior: list[float], transition: list[list[float]],
               emission_likelihood: list[float]) -> list[float]:
    """One causal HMM forward step; caller supplies frozen fitted parameters.

    No backward smoothing, future observations, parameter fitting or regime naming.
    """
    n = len(prior)
    if n == 0 or len(transition) != n or len(emission_likelihood) != n:
        raise ValueError("inconsistent HMM dimensions")
    for row in [prior, *transition]:
        if (len(row) != n or not all(finite_number(x) and 0 <= x <= 1 for x in row)
                or abs(sum(row) - 1) > 1e-6):
            raise ValueError("HMM distributions must sum to one")
    if not all(finite_number(x) and x >= 0 for x in emission_likelihood):
        raise ValueError("invalid emission likelihood")
    weights = [sum(prior[i] * transition[i][j] for i in range(n)) * emission_likelihood[j]
               for j in range(n)]
    total = sum(weights)
    if not finite_number(total) or total <= 0:
        raise ValueError("degenerate HMM posterior")
    return [w / total for w in weights]


def probability_metrics(rows: list[dict]) -> dict:
    """OOS Brier/log-loss/reliability by unique event; never unlocks calibration.

    Requires both prediction and outcome availability timestamps. Purging split
    overlap and grouping dependent events by session remain review requirements.
    """
    if not rows:
        return {"status": "NO_SAMPLES", "samples": 0, "calibration_ready": False}
    seen = set()
    for row in rows:
        if (not row.get("id") or row["id"] in seen or type(row["outcome"]) is not bool
                or not finite_number(row["probability"]) or not 0 <= row["probability"] <= 1
                or not all(aware(row[k]) for k in ("as_of", "trained_through", "label_available_at"))
                or not row["trained_through"] < row["as_of"] < row["label_available_at"]):
            raise ValueError("invalid evaluation row, duplicate event or temporal leakage")
        seen.add(row["id"])
    brier = sum((r["probability"] - r["outcome"]) ** 2 for r in rows) / len(rows)
    loss = 0.0
    for r in rows:
        p = min(1 - 1e-15, max(1e-15, r["probability"]))
        loss -= log(p if r["outcome"] else 1 - p)
    bins = []
    for i in range(10):
        bucket = [r for r in rows if min(9, int(r["probability"] * 10)) == i]
        bins.append({"lower": i / 10, "upper": (i + 1) / 10, "samples": len(bucket),
                     "mean_probability": sum(r["probability"] for r in bucket) / len(bucket) if bucket else None,
                     "observed_rate": sum(r["outcome"] for r in bucket) / len(bucket) if bucket else None})
    return {"status": "DESCRIPTIVE_OOS", "samples": len(rows), "brier": brier,
            "log_loss": loss / len(rows), "reliability": bins, "calibration_ready": False,
            "note": "Timestamp checks are necessary, not proof of independent, cost-aware OOS validation"}
