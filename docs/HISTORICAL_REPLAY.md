# Historical index replay v1

Run offline from `services/engine` with no provider credential:

```sh
python -m dantex.historical_replay --db /path/to/dantex-history.sqlite3 --output /path/to/new-run
```

The output directory must not exist. The archive is opened read-only, checked
with SQLite integrity verification, hashed before and after, and never used as
the forward validation store. The runner does not import the live recorder,
start observers, contact providers, execute orders, or alter frozen KT v1.0.

## Decision boundary

- Require known index identities and the original minute-candle source marker.
- Quarantine a date unless both indices have exactly the 375 expected regular
  minute bars. Invalid metadata, source, geometry, missing bars, and retained
  non-complete ingestion events also quarantine that date. This deliberately
  conservative coverage screening uses the completed archive, so it is a
  coverage-filtered research cohort, not a simulation of live data outages.
- Interpret provider candle timestamps as minute-open labels. Expose each
  complete candle only at timestamp plus one minute; no developing bar enters
  the prefix. This assumption must be independently certified before any
  production validation claim.
- At each cutoff pass only the current session's closed prefix to existing
  structure and momentum functions. Reset the prefix each session. No scaling,
  fitting, model selection, or parameter optimization uses later sessions.
- Call the existing shadow decision gate with missing readiness. Index candles
  cannot prove options, breadth, sector or volatility inputs; the correct full
  decision remains `NO_SETUP / NONE`. Structure and momentum remain descriptive.

## Outcome boundary

Outcomes are written separately after decisions. Fixed 5-, 15-, and 30-minute
labels use the next index bar's open as reference and a later closed bar as
endpoint. Reject noncontiguous/reordered label timestamps; censor horizons
extending beyond the current session. Preserve rejected decisions and censored
observations. No simulated option premium, broker fill, target-before-stop
ordering, or trade profitability is inferred from index OHLC.

The existing structure trend defines a descriptive directional cohort only.
The report shows index movement, high/low excursions, and hypothetical total
round-trip cost sensitivity at 0, 2, and 5 bps. These assumptions are neither
estimated execution costs nor option fees. Overlapping observations are not
independent trades; equal-session means avoid weighting sessions by the number
of directional observations, but are not statistical significance claims.

## Chronological validation blocks

The first 30 accepted paired sessions are development; subsequent fixed blocks
contain 20 sessions each. Ninety sessions produce three forward blocks. The
same rules run throughout, without tuning between blocks. These are temporal
engineering holdouts, not proof of untouched out-of-sample investment returns.
All hypotheses, failures, missing evidence, and censoring remain inspectable.

## Outputs and gates

- `decisions.jsonl.gz`: every timestamped historical observation and rejection.
- `outcomes.jsonl.gz`: independently labelled index movements and censoring.
- `report.json`: archive hash, coverage exclusions, session/block assignments,
  counts, descriptive summaries, limitations, and output hashes.

`calibration_ready=false`, `live_evidence_eligible=false`, and `probability=null`
remain fixed. Full outcome validation remains blocked on contract-specific
option history, spreads/Greeks, missing independent evidence, point-in-time
revision history, and defensible execution/cost assumptions. This stage does
not certify the provider calendar or reconstruct unavailable historical data.

## First archive run

The local 90-session archive (2026-05-20 through 2026-09-25) completed the
index-only replay with no quarantined dates. All 67,500 observations retained
`NO_SETUP / NONE`. The separate evaluator produced 193,500 observed horizon
labels and 9,000 session-end censored labels, across 5/15/30-minute horizons.
The split is 30 development sessions followed by three 20-session holdouts.
Output chronology, unique decision IDs, authorization gates and artifact hashes
were independently checked. The source archive hash remained unchanged.

These counts describe replay coverage, not successful trades or a passed
profitability test. Full historical option outcome validation is still gated.
