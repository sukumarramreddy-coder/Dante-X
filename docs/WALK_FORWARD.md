# Frozen-rule historical walk-forward diagnostics

This increment evaluates the frozen index-momentum component recorded by
`historical_replay`, using chronological partitions. It does not train a model,
fit thresholds, rank candidate strategies, recalibrate probabilities or authorize
execution. Context windows are descriptive development history, never training
input to an optimizer. Existing KT v1.0 and all calibration/live gates are unchanged.

## Workflow

From `services/engine`, use a completed replay database and new output filenames:

```powershell
python -m dantex.walk_forward plan `
  --replay C:\path\dantex-replay.sqlite3 `
  --output C:\path\walk-forward-plan.json

python -m dantex.walk_forward evaluate `
  --replay C:\path\dantex-replay.sqlite3 `
  --plan C:\path\walk-forward-plan.json `
  --output C:\path\walk-forward-report.json
```

Both stages open replay SQLite with the existing read-only snapshot connection.
Output files use exclusive creation and will not replace any existing file.
There are no broker, network, live-recorder, paper-lifecycle or calibration calls.
The index archive and backup are not opened by this command.

Freeze the plan before looking at performance. Planning uses session dates,
configuration and replay identities. It hashes label bytes to bind the input
without parsing outcomes or calculating performance. The plan includes the
evaluator source-byte hash, replay engine fingerprint, decision-chain head,
source-row digest, label digest and its own hash. Evaluation rejects changed
plans, changed source code, mixed versions and changed replay identities.

These are integrity checks, not a trusted external timestamp or signature.
Creating another plan after examining results does not restore an untouched
holdout. The report explicitly calls the final holdout a retrospective partition;
it cannot prove the historical dates were never inspected before this workflow.

## Default partitions

Defaults are `--initial 30 --test 10 --holdout 20 --embargo 1` session counts.
Sessions are actual ordered dates from the replay, not generated business days.
For 90 sessions, using one-based session positions:

| Partition | Context | Gap before evaluation | Evaluation |
| --- | --- | --- | --- |
| Fold 1 | 1–30 | 31 | 32–41 |
| Fold 2 | 1–40 | 41 | 42–51 |
| Fold 3 | 1–50 | 51 | 52–61 |
| Fold 4 | 1–60 | 61 | 62–69 |
| Final holdout | 1–69 | 70 | 71–90 |

Evaluation windows never overlap. Expanding context may contain earlier test
sessions, as is normal for a chronological walk-forward protocol, but rules stay
fixed and there is no fit step. Each gap is relative to that fold's context/test
boundary; a date evaluated in one fold can be a gap in the next fold. The final
holdout is reserved first, producing an eight-session last rolling window.
Insufficient history or invalid counts fail instead of shrinking the holdout.

## Label availability, sampling and metrics

Both context and evaluation partitions purge observations whose outcome horizon
ends after the partition's last session close. Label availability must be within
the partition. Purge counts and pre-purge label statuses are retained, so excluded
and censored outcomes remain visible. The source replay already prevents labels
crossing session close; the evaluator independently verifies this invariant.

The evaluation grid is fixed before outcomes: 09:16 IST plus integer multiples
of the replay horizon, separately for each symbol and session. With a 15-minute
horizon, candidate starts are 09:16, 09:31, 09:46, etc. Grid selection never skips
ahead based on direction, success, warmup or label availability. Unavailable,
neutral, quality-block and censored states remain in coverage counts but do not
receive a directional agreement score. A flat outcome counts as disagreement
for a directional CE/PE observation.

Reports separate NIFTY/BANKNIFTY and bullish CE/bearish PE component directions.
CE/PE here denote the existing component direction, not an option position.
For each group they show:

- eligible nonoverlapping complete horizons, agreements, disagreements and flats;
- descriptive direction-agreement rate and direction-adjusted index movement;
- session-level sample counts, rates and min/mean/max session rates;
- fold-by-fold rates, with final holdout metrics separate from rolling diagnostics;
- complete/censored label counts and component warmup/quality/unavailable counts.

Direction-adjusted basis-point moves are descriptive index measurements without
an entry/fill model, options, fees or slippage. They are not P&L. Nonoverlapping
horizons remain serially dependent, and the two indices remain correlated.
No confidence interval based on independent minute observations, aggregate trade
win rate, Sharpe ratio or significance claim is produced. Empty groups are null,
not a zero success rate. Global coverage omits pooled directional performance
so the final holdout does not get blended into development diagnostics.

## Input verification and remaining gates

Evaluation requires a successfully finished replay with both full index series
for every selected session. It streams and verifies the frozen decision chain,
each decision minute, source version, safety fields, label-to-decision links,
label reference price, horizon, finite numbers, directional consistency and
reported counts. Missing/orphan labels, invalid censoring or partial/failed
runs fail without writing a successful report. Consistency checks do not replace
independent verification against exchange data or a cryptographic owner signature.

Status `DIAGNOSTICS_COMPLETE` means the diagnostic job completed, not that a
strategy passed validation. Every report remains `historical_bootstrap`, with
`calibration_eligible=false`, `calibrated_probability=null` and
`execution_enabled=false`. There is no automatic pass threshold or promotion.
Full option evidence, premium outcomes, costs, independent forward validation,
and out-of-sample probability calibration remain outstanding. An attractive
agreement rate cannot unlock them.

Tests cover chronological splits, gaps, partial final windows, horizon purging,
fixed-grid sampling, null groups, hand-checkable metric arithmetic, deterministic
read-only/offline runs, modified protocols, corrupted audit/labels, malformed
inputs, and held-out outcome mutation that cannot affect earlier fold metrics.
