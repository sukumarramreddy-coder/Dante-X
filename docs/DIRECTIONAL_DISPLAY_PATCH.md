# Provisional directional display — Oct 1 patch

Based on PR #1 `build/foundation` head `eb18559b0782ffc2c1b4b785b662739194258158`.

The Overview and Signals screens now display the existing probability review's CE/PE percentages independently of paper lifecycle state and authorization. Fresh estimates are labeled provisional heuristic directional preference, uncalibrated and not profit odds. Conflict, stale or missing evidence retains the existing neutral 50/50 prior and is explicitly labeled prior-only. Missing or malformed engine responses display Unavailable, never a made-up percentage. Target-before-stop estimates and calibrated probability fields are unchanged.

The engine adds source blockers, missing families and stale/conflicting family reasons to the review. The dashboard independently reads `/v1/decision/current` to show the four-way review action, freshness, timestamp and missing inputs, including `validated_structural_plan`. Polling that endpoint does not initiate expert calls.

## Input diagnosis

- VWAP already flows from volume-weighted candles through structure snapshots into expert snapshots. The stored NIFTY/BANKNIFTY index candles lack usable traded volume, so VWAP remains unavailable. New finite/geometry/negative-volume guards prevent invalid input from emitting a numeric VWAP. No futures, ETF, simple-average or synthetic-volume proxy is substituted.
- V3 quote plumbing verifies instrument identity, response timestamp, last-trade timestamp and bid/ask geometry. It verifies prices/depth, not option-chain Greeks. `greeks_evidence_eligible=False` and `derivatives_evidence_eligible=False` remain intact. Available chain Greeks remain descriptive context; a timestamped, identity-matched Greek feed is still required before promotion.
- The four-way model has no validated structural stop/target, sizing or cost plan. Its premium values and directional scores cannot substitute for one. `validated_structural_plan` remains a blocker.
- `STALE_CONTEXT` is produced by closed sessions, historical fallbacks, missing/unparseable/future timestamps, provider stale flags, session mismatch or age over 180 seconds. The current review independently expires after 60 seconds. These gates remain intact; the app now exposes their reasons.

## Stored regression evidence

The source database was opened with SQLite `mode=ro`, retaining all 4,941 records: Sep 30 2,574; Oct 1 2,367. `scripts/verify_directional_replay.py` reproduces all 1,957 stored directional projections and all 1,957 four-way reviews. These are deterministic projection replays, not a new broker simulation, profitability validation or calibration run.

Oct 1 checkpoints retained in source-backed test fixtures:

| Sample | IST | Observation |
| --- | --- | --- |
| 2577 | 11:05:36 | NIFTY/Bank Nifty TREND_DOWN; PE score 3 versus CE 0 |
| 2582 | 11:06:08 | NIFTY failed breakdown / reversal forming up; CE 7 versus PE 3, while Bank Nifty stays PE |
| 4920 | 15:29:35 | Late NIFTY CE 3 versus PE 2; Bank Nifty CE 3 versus PE 0 |

All three remain blocked with no best executable candidate. The main Oct 1 family consensus has 323 PE rows and 613 conflict rows, with no CE consensus rows. Late CE preference belongs to the independent four-way review and must not be presented as consensus GO. Sep 30 has 292 CE consensus rows and 728 conflict rows. Fixture IDs and timestamps preserve provenance; fixtures are bounded projections, not a copy of the validation database.

## Safety and remaining work

No authorization routine, probability formula, calibration sample, learner, live mode, broker endpoint or stored validation row is modified. Live execution remains disabled. This increment updates the tracked web app; the local untracked Android project is outside PR #1's authoritative source. Phone installation and any running deployment still require a separate tested rollout. Verified Greek acquisition and structural plan validation remain future increments, with no fabricated fallback.
