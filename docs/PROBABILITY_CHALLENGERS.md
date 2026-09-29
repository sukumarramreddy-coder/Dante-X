# Provisional probability and offline challengers

`GET /v1/duel` returns `decision.probability` in **percent**, now numeric for a
fresh, DETECTED shadow option setup with valid premium geometry. The complete
`decision.probability_review` object is persisted with the decision in the
existing validation recorder and visible through `/v1/validation/recent`.
`GET /v1/challengers/status` exposes model availability without loading artifacts.

## Two distinct meanings

* `probability_review.directional.ce/pe`: a complementary, heuristic directional
  preference, bounded to 35–65%. It is **not** the probability of profitable CE/PE
  trades. Both options can lose money. Missing/stale/conflicting inputs produce a
  labeled `PRIOR_ONLY` 50/50, not an observed win rate.
* `decision.probability`: a provisional estimate for **T1 before stop within 30
  minutes or session close**, for the selected contract and reference barriers.
  The complement includes timeouts; it must not be called P(stop before T1).
  Without an eligible setup this stays null with an explicit unavailable status.
  Historical index-only ingestion/replay also retains null option probabilities:
  those records contain no eligible option contract or premium path.

All estimates preserve `calibration_ready=false`, `auto_execution=false`,
`read_only=true`, and shadow mode. The existing domain model still rejects an
unvalidated `calibrated_probability`. No probability changes the decision's
authorization, contract ranking, trade quality, sizing or execution gates.

## Frozen heuristic v1

One vote per known, already consolidated family; unknown/duplicated family names
cannot inflate the denominator or confidence. Numeric evidence scores and contract
execution quality are never treated as empirical frequencies.

```
strength = (CE family count - PE family count) / 8
strength = 0 if stale, conflicting or mixed CE/PE evidence
directional CE = 50 + 15 * strength
barrier prior = (entry - stop) / (T1 - stop)
alignment = strength for CE, -strength for PE
target estimate = 100 * clip(0.8 * barrier prior + 0.10 * alignment, 0.20, 0.60)
```

The barrier-distance prior is a simple driftless reference, discounted by a
**chosen**, untrained 20% factor for timeout/unknown dynamics. None of these
constants has been optimized against outcomes. For entry 100, stop 85, T1 120,
and eight aligned families, the estimate is 44.29%, while directional preference
is 65/35. Neither is a proven frequency. Validated sample support is **zero**;
there is no fabricated confidence interval or regime confidence. IV/theta,
slippage, fees, fills and actual horizon dynamics are not modeled in the estimate.
Only future, appropriately collected observations can assess whether it is useful.

## Challenger components in the build

| Component | Implemented boundary | Runtime state |
| --- | --- | --- |
| HMM regime | Causal forward-filter step over supplied frozen parameters | No fitted regime artifact; confidence unavailable |
| LightGBM / XGBoost | Trusted offline `predict_proba` adapter with exact feature order | No trained artifact configured |
| Qlib | Same binary probability adapter; raw return scores are not accepted as probabilities | No trained artifact configured |
| Meta-label | Same-contract 1-minute OHLC triple-barrier evaluator and binary model adapter | Offline evaluation only |
| Calibration | Unique-event Brier, log loss, reliability bins and temporal checks | Descriptive; no publication or automatic recalibration |
| Quantum-inspired optimizer | External proposal constraint validator plus exact small-set reference solver | No external quantum solver configured; no advantage claimed |

No external repository code, pretrained weights or optional ML dependencies are
bundled. These are usable offline interfaces/reference implementations, **not
trained models**. Regimetry/transformer and DeepLOB remain deferred until suitable
data and a separately reviewed artifact exist. Nothing is silently installed,
trained, blended or promoted during a live request.

### Offline model contract

`Provenance` identifies model/version, SHA-256 artifact identifier, feature schema,
training sample support, explicit `T1_BEFORE_STOP_30M_SESSION` target event and the
latest training-label availability timestamp. Directional models cannot be passed
off as target-before-stop models.
`predict_challenger` requires labels available strictly before inference and
features available no later than inference. A trusted caller owns loading the
artifact and verifying its digest; the adapter does not deserialize model files.
The binary class order must be `[0, 1]` for the declared T1-before-stop event.
It logs raw and shrunk/clipped review probabilities (fractions, unlike the live
percent API), feature values and timestamps. All challengers have zero decision
weight, no authorization and no calibration readiness. Raw .99 is never surfaced
as an incumbent 99% estimate.

`hmm_filter` is a pure numerical primitive, not a fitted regime engine. Offline
callers must ensure frozen parameters and causal emission features; posterior
state indices cannot be called risk-on/off without a reviewed state mapping.

### Labels and evaluation

`triple_barrier` consumes minute-boundary decisions and contiguous observed bars
from the exact option contract. It censors missing coverage, identity changes,
unclosed future bars and bars touching both stop and target. It never guesses
intrabar order. A fully observed timeout counts as false for the declared event.
This separate offline label schema does not relabel the recorder's existing
descriptive outcomes or treat index proxy returns as option outcomes. Session
hours use regular weekdays; exchange holidays/special sessions must be excluded
or separately reviewed by the dataset builder.

`probability_metrics` checks unique event IDs and training/prediction/label time
ordering. It does not prove independent OOS provenance: reviewers must additionally
purge overlapping label windows between folds, group dependence by session,
verify source/contract identity and compare to the frozen incumbent on identical
events. Count, Brier score or a favorable reliability bin never unlock calibration.

### Optimizer

`review_selection` expects rupee risk/reward/cost per candidate and fractional
review probabilities. Costs are included in the budget. At most one candidate per
caller-declared correlated exposure group is allowed; NIFTY and BANKNIFTY should
share a group when correlated. Non-target outcomes are conservatively priced as
full stops. The empty selection is valid. Up to 16 candidates are supported by
the exact reference benchmark; larger solver work requires a separate bounded
implementation. External proposals must pass the same constraints and cannot
produce orders. These hypothetical objectives are not realized profit forecasts.

## Promotion requirements

Promotion requires separate manual review of artifact provenance, chronological
purged walk-forward comparisons, same-contract outcomes, cost-aware results,
calibration stability by regime and sufficient independent samples. This change
does not implement a promotion switch, live training, model-upload endpoint,
broker execution or automatic self-adaptation.

## Verification

Engine tests cover numeric bounds, neutral fallback, correlation/deduplication,
zero-score conflicts, stale/invalid inputs, persistence and API safety flags;
challenger tests cover model schema/provenance, timestamp leakage, probability
validation, HMM filtering, known scoring-rule values, triple-barrier censorship,
budget/exposure rejection and zero authorization.
