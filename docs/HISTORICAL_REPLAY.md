# Historical index replay

This offline increment starts from foundation PR #1 at
`26827c8e9a3aa029b3530899c83aff91717c0048`. KT `1.0-frozen`, all existing
validation gates, and all execution settings remain unchanged. There are no
provider calls, orders, paper positions, fitted weights, or self-adaptation.

## Run

From `services/engine` in the checkout containing this increment, with the
engine dependencies installed:

```powershell
python -m dantex.historical_replay `
  --source C:\Users\sukum\Dante-X-Ingestion\data\dantex-history.sqlite3 `
  --output C:\Users\sukum\Documents\Codex\dantex-replay.sqlite3
```

The output **must not exist**. Choose a new filename for each rerun; do not
delete the source or backup. Optional `--start-date YYYY-MM-DD` and
`--end-date YYYY-MM-DD` select inclusive source sessions. `--horizon-minutes`
defaults to 15 (1..375 allowed). The printed JSON report also resides in the
last `replay_events` row. Exit 0 means selected sessions have both complete
375-minute index series; exit 2 reports partial coverage. Invalid source rows
raise an error; a started run records FAILED rather than a success report.
An interrupted output is retained for inspection and must not be resumed or
treated as a completed run. Start again with a new output filename.

## Clock and evidence

The source is opened through SQLite URI `mode=ro`, `query_only=ON`, with one
read transaction shared by decisions and labels. The ingestion store is never
opened for writing. SQLite's snapshot includes committed WAL content if any;
the replay does not checkpoint or modify the archive. Existing destinations,
including backups, hardlinks, symlinks, live databases and prior runs, are
rejected before writing.

Source timestamps mean **minute start**: the 09:15 candle first becomes known
at 09:16, and 15:29 becomes known at 15:30. Sessions have 375 decision records.
At 09:20 the 09:15–09:19 five-minute bar becomes available; at 09:30 the
09:15–09:29 fifteen-minute bar becomes available. Aggregation requires every
constituent minute and uses first open, max high, min low, last close and summed
volume. Zero index volume remains zero. OI is not turned into derivatives evidence.

`ReplayClock` only receives the current completed minute for each index, never
the archive connection or future paths. It uses bounded 60-bar windows per
timeframe and resets on missing minutes, clock gaps and session boundaries.
Existing `analyze_structure`, `momentum_family`, evidence-family synthesis and
`shadow_decision` are reused with their existing thresholds. 5m/15m structures
are context, never extra independent votes. The 21-bar structure warmup is
explicit; session-local 15m structure therefore first becomes available at
14:30. Prior-session warmup is not assumed.

This is reduced component evidence, not a reproduction of the complete live
engine. Live readiness is always false and option-dependent decisions are
NO_SETUP / operator WAIT / authorization NONE. Historical direction is retained
as descriptive component evidence, without inventing an executable contract.
Unavailable breadth, sectors, VIX, option chains, Greeks, spreads, premium paths,
prior-day and opening-range context are reported explicitly.

## Frozen audit and outcomes

The existing local `replay_capture.py` helper was reused, with an optional replay
clock timestamp. It includes an actual Python-source fingerprint. The local
`shadow_lifecycle.py` was inspected but is deliberately not invoked: its locked
option-contract transitions require fresh premium observations absent here.
The existing premium-path labeler is likewise inappropriate for index OHLC.

`replay_decisions` contains canonical JSON snapshots, engine/KT versions, known-at
times, completed input windows, structure/momentum states, the blocked decision,
and a SHA-256 chain. All decisions for a session are committed before the labeler
receives future bars. `replay_labels` references the frozen decision hash.
UPDATE/DELETE triggers protect audit tables against routine accidental edits;
hashes detect content changes but are not a cryptographic signature against a
database owner who can replace schema and recompute hashes.

Labels are **fixed-horizon index movements**, not trade wins/losses. A decision
known at 10:00 uses its already-known 09:59 close as reference, then the candles
starting 10:00 through 10:14 for a 15-minute label available at 10:15. Labels
include close change, basis-point return, maximum up/down excursions, UP/DOWN/FLAT,
and agreement with the frozen momentum direction where directional. Neutral,
warmup and quality-block states have no agreement score. Missing reference,
missing future minutes and end-of-session truncation are distinct statuses;
paths never cross sessions. No same-bar stop/target order or fill is inferred.
Overlapping observations must not be reported as independent trades or a win rate.

The final report includes per-index/session minute coverage, complete session
counts, decision/label counts, the decision chain head, and a logical digest of
the selected normalized source rows. The latter identifies replay inputs,
not unrelated archive metadata. No future-derived run digest enters predictions.

## Gates remaining

All records belong to `historical_bootstrap`. There is no `validation_samples`
table, forward recorder, external sink, lifecycle or calibration invocation.
`calibrated_probability` stays null and calibration eligibility stays false,
regardless of history length or directional agreement. Historical replay alone
cannot unlock probabilities. Full option evidence replay, premium/trade outcome
labels, costs/slippage, independent forward evidence, walk-forward evaluation
and the existing out-of-sample/calibration gates remain outstanding.

## Verification

```powershell
python -m ruff check .
python -m pytest -q
```

Run these from `services/engine`. Tests cover causal prefix equivalence under
future mutation, exact aligned completion boundaries, gaps/session resets,
durable freezing before labels, deterministic reruns, read-only source access,
output alias rejection, immutable audit records, censoring, invalid archives,
and separation from live validation/calibration.
