# Thirty-session learning window

The user-authorized live destination is **validated manual signals only**. Broker
orders remain impossible. `GET /v1/calibration/learning` reports progress and what
the model learned; the web dashboard polls it through a same-origin server proxy.
`GET /v1/signals/manual` publishes a current validated signal only after every
window and freshness gate passes. The original shadow decision and provisional
probability remain unchanged and explicitly uncalibrated.

## Collection and labels

The background observer now runs the same evidence/decision builder as `/v1/duel`.
No browser visit is required to collect a setup. New SQLite tables in a dedicated
learning database retain the prediction, model identity, source bars and outcome.
They survive restarts on a persistent local volume. Legacy index replay and
descriptive recorder labels are never mixed into this window.

Only fresh DETECTED setups with a provisional probability can enter. The current
decision builder's universe is NIFTY options. A global 30-minute embargo prevents
overlapping/correlated setup observations. The event starts at the first complete
minute after prediction and uses the precommitted reference premium barriers.
This deliberately assumes no fill; it estimates reference barrier behavior.
New events require a full 30 minutes before regular session close.

After the horizon, read-only intraday candles are fetched for that exact option
key. Missing bars, changed identity, invalid data and ambiguous intrabar double
touches are censored. No next-day historical backfill silently repairs a missed
live outcome. Raw bars and the result are stored; labels cannot be overwritten.

Option path prices/depth are now replaced with identity-matched full V3 quotes.
Both provider response timestamp and last-trade time must be fresh; receipt time
alone is insufficient. Chain Greeks/IV remain unverified context and cannot unlock
the derivatives family. See [Upstox V3 quote semantics](https://upstox.com/developer/api-documentation/get-full-market-quote-v3/).

## What learns, and when

A qualifying session is a completed trading date with at least **five** resolved,
non-overlapping outcomes. Empty, partial, holiday, offline and ambiguous-data days
do not count just because time passed. Valid outcomes from low-coverage sessions
still affect fitting/evaluation: they cannot be dropped to improve results.

The first **20 qualifying sessions** fit a beta-smoothed frequency for each
CE/PE and original ten-percentage-point score band: `(wins+5)/(samples+10)`,
bounded to 20–65%. This is a deliberately small calibrator, not training all
unconfigured HMM/boosting/quantum challengers. Training estimates are visible but
are not published as validated probabilities.

The model, its SHA-256 identity and freeze timestamp are fixed before any
validation prediction. The next **10 qualifying sessions** are untouched holdout:
each event stores the probability from that exact frozen model. There is no
adaptive retraining on a disappointing holdout. Reopening the database does not
reset the split, refit the model or relabel completed events.

## Automatic manual-signal gate

After all 30 qualifying sessions, `calibration_ready` may become true **for the
learning window/manual signal endpoint only**, if all these predeclared gates pass:

* At least 100 training and 50 held-out resolved outcomes, with verified durable storage.
* Validation Brier better than the original provisional estimate, and no more
  than 0.01 worse than the fixed training base-rate predictor.
* Weighted calibration error no greater than 0.10.
* A published band has at least 20 training and 20 validation outcomes, with
  absolute band calibration error no greater than 0.10.
* Positive lower bound on equal-session mean cost-stressed reference return:
  daily mean minus 2.3 standard errors. Hypothetical round-trip costs are stressed
  at 2% of entry premium; timeouts lose a full stop. These are assumptions, not
  actual brokerage/fills or a guarantee of profitability.
* Current setup freshness and authorization still pass. A published snapshot
  expires in 60 seconds. Validation older than 30 calendar days is blocked.

These thresholds are a versioned operating policy, not a claim that 30 sessions
establish permanent calibration. A failed window stays `VALIDATION_FAILED` and
lists specific blockers. Continuing to test new models requires a separately
reviewed new window; this implementation never repeatedly tests the same holdout
until something passes. No environment flag simply forces readiness true.

The report includes session dates, admitted/pending/censored counts, learned
bands and their support, Brier/log-loss/reliability, model hash, collection status,
cost-stress results and readiness blockers. The dashboard distinguishes an
unavailable recorder from zero samples and clears old manual signals on refresh.

## Local activation

Install the engine and web dependencies and build the web app first. On Windows,
run `scripts/start-learning.ps1` with `-PythonPath`, `-NodePath`, `-DataDir` and
optionally `-CredentialsFile`. Defaults are localhost engine port 8010 and web
port 3010. The bootstrap uses hidden background processes and creates log/PID
files in the specified data directory. It doesn't stop or replace existing
services. `scripts/run_learning.py` reads only Upstox token entries from the
credentials file; it does not copy credentials into logs or learning artifacts.

When Windows PowerShell script execution is disabled, use `scripts/start_learning.py`
with `--python`, `--node`, `--data-dir`, and `--credentials-file` instead. The local
autostart task uses this Python launcher; no Windows execution policy is changed.

The data directory must be a persistent, backed-up location outside temporary
folders. Temporary paths cannot be declared durable by an environment flag. The
Render free-tier configuration is intentionally unchanged: its temporary disk
does not satisfy the learning durability gate. The local computer must be awake,
connected, and have valid provider credentials during market hours. Autostart
cannot collect while the computer is off. No calendar end date is promised.
