# Android / local rollout — Oct 1

The original local Android console read per-index probability fields under
`final` that the engine does not produce. The corrected 0.2.0 console reads the
additive `probability_review` on `/v1/decision/current`. This is the existing
NIFTY heuristic with BANKNIFTY confirmation, not independent per-index profit
odds. Each index separately displays the four-way evidence scores and blockers.
The client never rescales a 1% value to 100%, invents percentages, reads model
advice as calibration or changes authorization.

`DecisionRuntime` attaches the existing bounded heuristic after reconciliation,
so action and authorization cannot be affected by it. Expired output exposes a
neutral prior and stale reasons. On restart the most recent persisted expert
review is recovered through query-only SQLite access and always marked stale,
even if its timestamp is recent. Older records without directional provenance
receive only the explicit neutral prior. Existing validation rows are unchanged.

The debug APK uses the existing trusted-LAN address `192.168.1.104:8000`.
Android unit tests and debug assembly run locally, with a new Android CI workflow.
Installation requires an authorized connected phone or manually installing the
delivered APK. A successful build does not establish installation on a phone.

## Unresolved inputs

The official Upstox REST option-Greek response includes instrument identity but
does not document a Greek source timestamp:
https://upstox.com/developer/api-documentation/option-greek/
Retrieval time and the last-trade time of a separate price quote cannot be
manufactured into a Greek source timestamp. A timestamped option stream with
matching identities, numeric bounds, synchronization and fail-closed freshness
tests is still required. No unverified Greek field is promoted in this increment.

Validated structural plans still require structural invalidation, contract
sensitivity, expiry, sizing and costs plus independent replay validation. Those
inputs are unavailable; `validated_structural_plan` remains a blocker. No
percentage stop or synthetic target is substituted. Index VWAP still needs
actual traded volume. Calibration and live execution settings are unchanged.
