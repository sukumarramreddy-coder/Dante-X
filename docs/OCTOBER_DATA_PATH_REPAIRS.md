# Oct 6 probability and October outcome audit

Authoritative branch: build/foundation, PR #1. Existing head be4869924d5c1d23609e1240f3fa56eb74bc3083 already contains the Oct 5 outcome-queue repair. This change completes the uncommitted response-clock repair and adds a historical-backlog maturation regression. No launcher, UI or networking files are included.

## Probability root cause

Query-only audit confirms Oct 6 has 1,960 rows including 184 CE_EVIDENCE, 273 CONFLICT, 189 NO_EDGE and 646 EXPERT_REVIEW. All 646 probability reviews lack fresh evidence. Oct 5 has 1,378 fresh reviews of 1,380 expert reviews.

The previous diagnostic audit found Oct 6 response timestamps ahead of recording time by a median 0.4375465 seconds, maximum 0.564042 seconds. Breadth, sectors and VIX diagnostics explicitly report future source timestamps. The gate previously rejected any negative response age. V3 option verification uses this same gate and clears path history after failed verification. Raw failed option responses were not retained, so their precise rejection cannot be independently reconstructed; regression tests reproduce the observed failure with the measured clock offset.

A fixed one-second allowance now applies only when explicitly requested for quote response timestamps. It does not apply to exchange trade times, candles or path observations. Responses beyond that allowance still fail; the 180-second stale threshold and all other readiness checks remain unchanged. No timestamps are rewritten or replaced with receipt time. CE_EVIDENCE alone does not establish complete freshness readiness.

## October outcomes

Read-only audit of the preserved database:

| Session | Rows | Directional DETECTED setups | Labelled outcomes |
| --- | ---: | ---: | ---: |
| Sep 30 | 2,574 | 292 | 6 |
| Oct 1 | 2,423 | 323 | 0 |
| Oct 5 | 3,471 | 450 | 0 |
| Oct 6 | 1,960 | 0 | 0 |

The old unlabelled query selected the first 200 rows before filtering decision eligibility. The current DB reproduces its blocking prefix exactly: 200 unlabelled Sep 30 rows, all ineligible (1 observation failure, 82 expert reviews, 41 market observations, 76 NO_SETUP). The tracker skips them without removing them, permanently starving later eligible setups. Historical cross-session paths also cannot provide valid same-session outcomes.

This bug is already fixed in be48699: eligibility and process-start filtering occur in SQL before LIMIT; paths consume only verified contract prices during the forward horizon; incomplete paths are censored and released. The added regression proves a new directional setup matures after 200 ineligible historical rows and an old eligible row, while all pre-start rows remain identical. Existing tests cover missing, stale, future and gapped observations.

No further production outcome change is required for the reported starvation. Missing historical observations are not fabricated or backfilled. Existing October outcomes remain unlabelled. The separate learning store and its calibration admission gates are unchanged. Oct 6 has no eligible directional setup because its freshness readiness failed.

## Files and validation

- services/engine/dantex/freshness.py: opt-in bounded response-clock tolerance.
- services/engine/dantex/providers/verified_option_quotes.py: V3 response opt-in; strict trade timestamps retained.
- services/engine/dantex/api.py: response opt-in for breadth, sectors and VIX.
- services/engine/tests/test_quote_clock_skew.py: 19 regression cases.
- services/engine/tests/test_session_repairs.py: historical queue and new forward maturation regression.
- docs/OCTOBER_DATA_PATH_REPAIRS.md: this audit.

Full engine suite: 350 passed, 2 existing deprecation warnings. Ruff and diff whitespace checks passed. Tests use isolated validation, learning and engine DB paths in the current chat workspace; external validation sink variables are cleared.

Validation SQLite SHA-256 before and after:
C38A7875F4FF183E8C21F4527B7893E1938B89F70316C24DCF6B070124CC0901

No production SQLite write connection was used. SHADOW/read-only behavior, calibration gates and live-execution restrictions remain intact. Historical rows remain unchanged. The running engine was not restarted; it needs to load updated source for subsequent sessions. Fresh verified option samples must rebuild option-path baselines.
