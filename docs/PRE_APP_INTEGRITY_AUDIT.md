# Pre-App Integrity Audit — 2026-09-28

Baseline: PR #1, `build/foundation`, freshly verified head
`26827c8e9a3aa029b3530899c83aff91717c0048`. Baseline engine and web CI passed.

## Preserved constraints

Frozen KT v1.0 and its tests are unchanged. Runtime remains read-only/shadow;
no broker execution or self-adaptation was added. Historical replay and
walk-forward validation remain the next stage. No merge is authorized.

## Fixed

- FastAPI startup now uses lifespan rather than deprecated event registration.
- Temporary SQLite and a configured-but-failing external sink cannot prove
  durable readiness. A persistent local volume requires explicit operator
  attestation; known temporary paths are always excluded. External health
  requires a successful write within 60 seconds and no subsequent error.
- Diagnostic heartbeats cannot refresh stale market observations. Shadow
  observation freshness does not grant live authorization.
- External sink configuration requires HTTPS without embedded credentials or
  query parameters; redirects are refused to avoid forwarding authentication.
  Failed sends preserve the local record and expose sanitized failure state.
- Public exception diagnostics and credential object representations no longer
  echo exception bodies, tokens, or signed URLs.
- Provider heartbeats require finite positive prices, the subscribed identity,
  and fresh exchange timestamps. Missing/ambiguous/future timestamps fail closed.
- Option-chain receipt time is not proof of exchange freshness. These snapshots
  remain descriptive and cannot qualify for live evidence or outcome labels.
- Outcome labels reject pre-decision, unordered, cross-session, future-dated,
  and invalid-price rows. This is boundary validation, not historical replay.
- Calibration bands remain descriptive. Even 100 samples cannot set
  `publishable=True` without the separate validation stage. The positive-count
  test was tightened to enforce that gate; no existing tests were removed.
- Web health responses cannot enable live mode or calibrated probability.
  The static terminal shell now displays its demo status in the header.
- Added a reproducible npm lockfile, compatible PostCSS 8 patch override,
  web contract tests, TypeScript checking, dependency audit, deployment contract
  test, and Docker build/health smoke CI. No major framework upgrade was used.

## Architecture reconciliation

`dantex.api:app` is the deployed read-only diagnostic/observation API. The
orchestrator, signal store, settings, and other domain modules are foundation
components tested separately; they are not a fully wired production app.
`DANTEX_MODE=live` in the settings scaffold denotes observation configuration,
not broker execution permission. Render and Docker both remain shadow.
The web page is an illustrative static shell; `getRadar` is a fail-closed
adapter scaffold, not a connected live radar. No domain modules were deleted
solely because the deployed API does not yet import them.

## Gated / next-stage work

- Proven option-chain exchange freshness and end-to-end provider identity must
  precede live evidence eligibility. Current unproven chain data is gated.
- Historical and synthetic archives never unlock calibration; publication is
  disabled. Historical replay, OOS/walk-forward validation, costs, regime and
  instrument-family validation remain unimplemented next-stage work.
- External inserts are a best-effort observation sink. Durable label sync,
  restart recovery, retry reconciliation, and a complete remote dataset are
  not proven. Recent successful inserts do not establish calibration readiness.
- Production persistence requires operator verification of the configured
  service/volume and backup recovery. Tests use controlled failures, not private
  deployed credentials. No production data or provider credentials were used.
- Daemon observer shutdown/restart orchestration and full app wiring remain
  integration work; lifespan migration preserves the existing startup behavior.

## Local archive verification

Both `dantex-history.sqlite3` and `dantex-history-BACKUP.sqlite3` in the user's
Windows ingestion data directory were opened read-only. Both returned `ok`
from `PRAGMA integrity_check`, were unchanged during verification, and have
identical SHA-256:
`3e1d5e403340e7e6f53949a6aa3be08360d1296be40df6f2d8b1ae8afdf32eef`.
Each contains 67,500 candles: 90 distinct sessions and 33,750 candles for each
of NIFTY and BANKNIFTY. This proves file integrity and matching backups at
audit time, not source-market accuracy or suitability for options calibration.
