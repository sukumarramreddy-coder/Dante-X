# Optional expert review and Android decision contract v1

The existing observer collects options and structure. Its existing duel cycle now
builds one bounded snapshot, independently reviews NIFTY CE/PE and BANKNIFTY CE/PE,
optionally requests structured OpenAI advice, reconciles under deterministic risk
rules, and stores the result in `validation_samples` as `EXPERT_REVIEW`.
No second service, order endpoint, broker write capability, or learning model is added.
Frozen KT v1.0 and the existing manual-signal/calibration interfaces are unchanged.

## Configuration

Backend environment only: `OPENAI_API_KEY`, `DANTEX_OPENAI_ENABLED` (default false),
`DANTEX_OPENAI_MODEL` (required when enabled; operator-selected Structured Outputs
capable model), `DANTEX_OPENAI_TIMEOUT` (8 seconds, bounded 1–30),
`DANTEX_OPENAI_MAX_CALLS_PER_MINUTE` (2, bounded 1–60), and
`DANTEX_OPENAI_INTERVAL_SECONDS` (60, bounded 10–3600).
Never put the key in Android or NEXT_PUBLIC variables. No live API call is required
for tests. Invalid/incomplete/refused responses and provider failures fall back.

Responses API uses strict JSON schema, `store=false`, no tools, bounded input/output,
and rejects credential-bearing redirects. A local call budget covers failed attempts.
Identical snapshot caching expires after 60 seconds. Regime, impulse, candidate and
position events may bypass the interval but never the rate budget. Limits/cache are
per process; multiple workers need a shared budget before enabling at scale.

## Additive endpoints

* `GET /v1/decision/current`: cached observer result; never calls OpenAI on UI polling.
* `GET /v1/decision/history?limit=50`: persisted evaluations and nullable later outcomes;
  maximum 200 entries.
* `GET /v1/expert/status`: enabled/configured/model/state; no credentials.

Current results use `schema_version: "1.0"`, `timestamp`, `feed_fresh`, `missing_data`,
`deterministic` and `final`. Before the first observation, `timestamp` and
`deterministic` are null and status is PENDING. `deterministic.candidates` contains
four independent instrument/side evaluations; `regimes` is per index.
`final.action` is authoritative; `final.expert_advisory.advice` is optional,
unvalidated commentary, never an execution instruction. More than 60 seconds old
sets `feed_fresh=false`; stale HOLD becomes PROTECT, but EXIT remains EXIT.

Android must display null as unavailable, label expert percentages as unvalidated
model estimates, and keep evidence scores separate from probabilities. Continue
using `/v1/signals/manual` for the existing validated manual signal. Do not turn an
expert GO or a `shadow_candidate` into a live notification or trade authorization.
Use `audit_sample_id` for later review; absence/UNAVAILABLE means logging failed.

## Measurable rules and scope

Each cycle recomputes both sides from current structure/path evidence. An impulse
is a close-to-close move at least 1.5 times the preceding mean bar range. Failed
extension and existing option-refusal states trigger opposite-side review. RSI is
a descriptive 14-change gain fraction; it is not an independent confirmation vote.
Position ownership never changes the four-way scores. Independent market, premium,
and maximum-risk invalidations each force EXIT. Missing position risk fields force
PROTECT. Averaging is not enabled.

Option quality reuses execution score, adds delta fit, expiry theta stress and an
ATM expansion penalty; intrinsic/extrinsic amounts and delta-only move sensitivity
are exposed. No guessed cheap/fair valuation, structural stops, targets, payoff odds
or risk/reward are invented. These stay null where unsupported. The 11:00 checkpoint
returns NO_EDGE rather than an indefinite new-entry WAIT; it never suppresses the
pre-existing manual-signal engine before 11:00.

## Explicit limitations and freeze decision

This is an advisory integration, not completion of every feature in the final-push
specification. The new four-way model has no matching validated calibration artifact
and cannot issue GO; existing calibrated manual signals remain independent. Chain
Greeks are currently marked unverified by the provider. Bank constituent/PSU-private
divergence, macro/news feeds, per-contract premium basing and a validated option
valuation model are not connected. Missing sources are exposed rather than invented.
The internal position governor accepts position state, but no live broker position
adapter or Android position-entry API is introduced. Automatic outcome linking for
expert reviews is not implemented; the existing recorder can attach later labels.
Historical index replay does not validate option profitability or expert accuracy.

Android can implement this versioned read-only contract. Do not call the entire
engine certified or freeze live trading behavior until those product gaps, external
persistence/restart checks, live feed recovery, and calibration gates are resolved.

## One-command audit

From `services/engine`, after `pip install -e ".[dev]"` and frontend `npm ci`:

```text
python -m dantex.pre_app_audit --full
```

Optional `--archive`, `--backup`, `--expected-sha256`, and `--output` override defaults.
The default archive paths are under the current user's Dante-X-Ingestion/data.
Every run uses a new output directory, checks source/backup hashes, validates paired
90-session/67,500-row coverage with the existing strict loader, and runs a fresh
isolated descriptive replay. Existing replay directories are never removed.
The command runs engine tests (including KT, no-look-ahead, isolation, provider and
deployment contracts), lint, web tests/typecheck/build and a heuristic source scan.
Full mode probes configured Upstox authentication and writes/reads a unique external
DIAGNOSTIC row, which cannot become a training observation. It never restarts a
deployment or deliberately disconnects a live feed.

Statuses: CLEAN means the named automated check passed; GATED means failure;
PENDING means missing configuration/evidence; USER ACTION means an unperformed real
operational check. FIXED is reserved for a documented repair followed by revalidation;
the runner does not auto-repair evidence or claim FIXED. Exit 1 means critical
failure, exit 2 critical pending/user action, exit 0 all selected checks passed.
Without --full, exit 0 says OFFLINE_CHECKS_CLEAN, never full certification.
JSON summary and redacted command logs are retained. The security scan is heuristic,
not a complete Git history secret audit. Install dependencies separately so audits
do not modify lockfiles or fetch changing dependencies implicitly.

References: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
and [Supabase Data REST API](https://supabase.com/docs/guides/api).
