# Historical session bootstrap (shadow research only)

Dante can import the last 90 provider-reported trading sessions of NIFTY and
BANKNIFTY one-minute OHLCV/OI candles. This is **index price history**, not a
historical options-chain replay, trained model, or calibrated win probability.

From `services/engine`, with the existing server-side `UPSTOX_ANALYTICS_TOKEN`
configured securely, run:

```sh
python -m dantex.historical_ingestion --db /persistent/dantex-history.sqlite3 --sessions 90
```

On Windows, use a separate persistent file, e.g. `--db C:/Users/sukum/Dante-X/data/history.sqlite3`.
Never paste tokens into arguments, logs, Git, or the browser. The importer only
calls existing read-only historical-candle methods. It does not run on API startup,
make live decisions, change observer timing, or create public mutation endpoints.

The default end date is **yesterday in IST**, avoiding a still-forming or settling
current session. To ingest through 25 September, run on 26 September or later with
`--end-date 2026-09-25`. Run the same command after each completed day to accumulate
history safely. A 365-calendar-day discovery window is bounded; if fewer than 90
sessions are available the report remains PARTIAL rather than inventing weekdays.
Dates are the union of both indices' daily bars, not a weekday-only calendar. A
missing daily bar for either index is flagged. This is provider-reported coverage,
not independent exchange-calendar certification: an outage affecting both daily
feeds can omit a date, so certify against the exchange calendar before calibration.

Minute requests are made separately for each date and index, in chronological
order, with a 0.4-second pause per request. This respects the documented V3
one-month maximum for one-minute candle requests. HTTP 401/403/429 stops the run;
configure credentials or wait for the provider limit to clear, then rerun. Other
failed days are logged and the job continues. No error response bodies are saved.

## Persistence and completeness

- An explicitly selected **separate persistent SQLite file** is mandatory. The
  importer refuses a database containing `validation_samples`. Do not use Render's
  ephemeral `/tmp` for the durable historical archive. This job requires an
  existing credential-bearing runtime with persistent disk; deploying the code
  alone does not run the import or provision storage.
- `historical_candles` retains original normalized timestamps, exact instrument
  keys, values, source and first ingestion time. Identical rows are deduplicated;
  revised prices are reported as conflicts and never overwrite prior evidence.
- `historical_import_events` appends STARTED, each session result, and FINISHED
  manifests under a unique run ID. Interrupted jobs retain committed sessions and
  have no FINISHED event; rerunning fills gaps without deleting history. Run one
  importer per archive at a time. Back up the archive using SQLite's backup API.
- COMPLETE_REGULAR_SESSION requires all 375 distinct one-minute bars from 09:15
  through 15:29 IST, valid OHLC geometry, finite numbers, correct timestamps, no
  conflicting duplicates, and no invalid or outside-hours rows. Short/special
  sessions are conservatively PARTIAL, not fabricated to fit normal hours. This
  historical minute window differs from live context recording through 15:39.
- Exit 0 means all requested index sessions meet that coverage check; exit 2 means
  partial/blocked. Neither means calibration passed. Zero index volume is retained
  as zero, not converted to synthetic VWAP or option volume.

Inspect records chronologically using `ORDER BY ts` and the session manifests.
Downstream replay must only consume candles available at each simulated time.
Historical rows are isolated from the live validation recorder and have no live
authorization. Reports explicitly return `calibration_ready=false`,
`live_evidence_eligible=false`, and `probability=null` even on successful ingestion.

## What remains for full calibration

Historical contract-specific option chains/prices, spreads, Greeks and other
independent evidence families are not reconstructed from index candles. Outcome
labelling, chronological replay, costs and held-out walk-forward validation remain
separate work. No probability or performance claim is justified by this import.

Provider reference: [Upstox Historical Candle Data V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/).
