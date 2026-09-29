# Dante X dashboard

The local research dashboard reads the existing engine. Overview shows NIFTY/BANKNIFTY, structure, evidence families, freshness, and the current SHADOW decision. Options provides both nearest-expiry chains. Journal displays the latest 50 saved observations with a decision filter and record details.

## Run locally

With Node.js and pnpm installed, from `apps/web`:

```sh
pnpm install --frozen-lockfile
pnpm build
pnpm exec next start --hostname 127.0.0.1 --port 3000
```

For development use `pnpm dev`. The engine must be running on port 8000. To override its address, set the server-only `DANTEX_ENGINE_URL` variable in `apps/web/.env.local`. Never put broker credentials in browser environment variables.

The same-origin `/api/dashboard` bridge uses a fixed endpoint list, individual timeouts, no caching, and independent failure handling. It calls the existing duel endpoint, which persists a decision; opening the dashboard and refreshing it therefore adds ordinary validation records. Refresh runs every 30 seconds while the page remains mounted. Market information can differ slightly between independently fetched endpoints.

The Signals view integrates a persistent SHADOW premium lifecycle: WAIT, GO, HOLD, RUN, WARNING, EXIT and CANCEL. The original setup scan remains DETECTED/NO_SETUP. GO means a later fresh observation reached the locked reference premium, not an order or assumed fill. Both CE and PE are modeled as long-option premiums. The existing entry cutoff (15:10 IST) and force-exit policy (15:20) remain in effect. Session closure never invents an exit price. Missing/stale evidence or a missing locked contract quote pauses tracking with no authorization. Only NIFTY is selected by the existing decision routine; BANKNIFTY remains confirming context. New signal state and transition history are stored in separate SQLite tables in the existing validation database. The observer evaluates signals during market hours without requiring an open dashboard. No calibrated probability, AI-model signal generation, broker execution, or public deployment is introduced. The dashboard labels closed/stale context and never substitutes demo values for failed fetches. Probability is intentionally displayed as not calibrated. The journal is limited to its latest batch; its filter does not search the whole database.

Before public hosting, add an appropriate access-control layer. This build is bound to loopback for local use.

