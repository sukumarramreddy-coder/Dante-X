# Dante X

Dante X is a **read-only, multi-market intelligence and signal research platform** for Indian markets.

It is designed to scan an approved universe, maintain competing bullish and bearish hypotheses, measure live confirmation and expected-vs-actual market response, enforce explicit risk/reward, and produce auditable signal plans for **manual execution**.

> Dante X does not place broker orders. It is an intelligence layer, not an autotrader.

## Permanent architecture

- `apps/web` — operator dashboard: Radar, Focus, Live Trade, Events, Lab
- `services/engine` — deterministic FastAPI analytics, signal lifecycle, risk and ranking
- `docs` — architecture, signal contract and validation rules
- `.github/workflows` — CI
- provider adapters — market data only; broker order endpoints are intentionally excluded

## Core signal lifecycle

`NO_EDGE → DETECTED → WATCH → ARMED → GO → HOLD → RUN → WARNING → EXIT/CANCEL`

An **ARMED** trigger is immutable merely because price approaches it. It may fire, be explicitly cancelled by fresh evidence, or expire.

## Confidence model

Dante X separates:
1. **Live confirmation** — independent expected behaviours occurring now.
2. **Path match** — actual path versus the setup's expected path.
3. **Potential left** — remaining opportunity versus invalidation/costs.
4. **Calibrated probability** — disabled until out-of-sample validation supports it.

No LLM-generated percentage is represented as a win probability.

## Safety and execution

- Read-only market intelligence.
- No broker order placement.
- No secrets in source control.
- Quantity is computed *after* structural invalidation and risk budget.
- Intraday and positional horizons are explicit before entry.
- Failed intraday trades are never silently converted into overnight positions.
- Every signal decision is timestamped and auditable.

## Status

Core foundation is implemented on the foundation branch: signal lifecycle, two-sided hypotheses, market-response intelligence, execution/risk gates, immutable triggers, shadow simulation, audit persistence, calibration scaffolding, Radar API contract and terminal UI shell.

The system intentionally remains **SHADOW / research mode** until a production market-data provider is connected and historical walk-forward validation makes probability calibration publishable. See `docs/PRODUCTION_READINESS.md`.

### Next external inputs

To cross from code-complete foundation to validated live intelligence, the project needs:
- approved read-only live market-data credentials/provider
- a normalized historical dataset suitable for walk-forward validation
- a deployment target for the engine/UI

These are operational inputs, not reasons to weaken the safety gates.

### Historical bootstrap

The read-only historical importer can accumulate the last 90 provider-reported
NIFTY/BANKNIFTY sessions in a separate, append-only index-candle archive. It reports
coverage and missing inputs; it does not claim options calibration. See
[Historical ingestion](docs/HISTORICAL_INGESTION.md) for the command and storage requirements.
