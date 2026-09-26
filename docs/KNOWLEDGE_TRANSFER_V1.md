# Frozen Knowledge Transfer v1.0

**Status: FROZEN until the current Dante X read-only probability-engine build is complete.**

This document is the canonical transfer of durable reasoning rules developed during manual Dante/Dante-X work. It is deliberately compact and testable. Conversation history, emotional context, rumors, one-off trades and unvalidated heuristics are not runtime knowledge.

## Mission

Dante X Phase 1 is a read-only, evidence-driven market intelligence and probability research engine for manual execution. It must observe, reason, freeze decisions, record outcomes and accumulate calibration evidence without placing broker orders or rewriting its own strategy.

## Permanent reasoning boundaries

1. Maintain bullish and bearish hypotheses independently. Existing holdings never bias direction.
2. Direction and instrument quality are separate decisions. A bullish index thesis does not imply that a particular CE is executable; IV, theta, spread, liquidity, premium response and net R:R can still require WAIT.
3. Price/market response outranks narrative. News and external events provide context, not authority.
4. Use independent evidence families; correlated indicators do not become multiple confirmations.
5. Natural structural invalidation comes before stop distance, risk budget and quantity.
6. Net reward/risk after estimated costs and slippage is mandatory.
7. Potential left matters. Do not chase a mostly spent move merely because direction is correct.
8. Intraday is classified before entry and must exit the same session. It never silently becomes positional.
9. Preserve failures, blocked setups and rejected opportunities. Learning evidence must not erase inconvenient outcomes.
10. Once sufficient evidence authorizes GO, do not create endless confirmation creep. A valid evidence-based loss is acceptable; hesitation after authorization is a process failure.
11. No edge is a valid conclusion. Zero trades is preferable to manufactured conviction.

## Evidence domains

The engine may reason from:
- price structure, opening range, support/resistance, break/retest/failed-break behavior
- 1m source data with aligned completed 5m/15m structure; forming higher-timeframe bars are not confirmed
- EMA/VWAP/RSI/momentum and displacement
- volume, liquidity, absorption, depletion/replenishment and execution quality
- NIFTY/BANKNIFTY, breadth, sectors and related-market confirmation
- option chain, OI/PCR, IV, Greeks, expiry, premium response, spread/liquidity and costs
- external events/news only as supporting context
- opportunity quality, structural invalidation, targets, R:R and remaining potential

## Operator vocabulary

User-facing actions are exactly:

**WAIT / GO / HOLD / PROTECT / EXIT**

The internal lifecycle may remain more granular: NO_EDGE → DETECTED → WATCH → ARMED → GO → HOLD → RUN → WARNING → EXIT/CANCEL.

## Probability and calibration law

- Live evidence confidence/path match/potential-left may be visible during calibration.
- A model score or provisional confidence is **not** a measured win probability.
- calibrated_probability remains gated until real out-of-sample evidence satisfies validation.
- Historical bootstrap, forward observation and calibration gates are distinct evidence stages.
- 30/60/90 sessions are review checkpoints, not automatic permission to publish probability.
- Synthetic/demo evidence cannot unlock real calibration.
- Material reasoning changes invalidate stale calibration until revalidated.
- Frozen predictions must be scored against subsequent market outcomes without look-ahead.

## Initial calibration law

During the initial controlled calibration period:
- evidence and outcomes accumulate append-only;
- the foundational KT/rules/weights do **not** self-adapt or self-rewrite;
- daily digestion means recording and summarizing evidence, not mutating old evidence;
- historical evidence must not contaminate forward-validation evidence;
- current failures remain visible.

## Phase-1 safety boundary

- Read-only market-data access.
- No broker order placement.
- No autonomous or paper execution in this completion phase.
- Stale/missing/unsynchronized required data fails closed.
- No averaging, chasing or revenge flip authorization.
- Risk governance remains external to directional conviction.

## Explicit exclusions

KT v1.0 does **not** include:
- conversational clutter or emotional reactions;
- fabricated or hypothetical trades as evidence;
- rumors as facts;
- hidden LLM percentages presented as probabilities;
- self-modifying safety/calibration gates;
- the later VIX-to-moneyness heuristic (>20 OTM / 12–20 ATM / <12 ITM), which is intentionally retained only as a manual-analysis heuristic unless independently validated and explicitly promoted later.

Implementation reference: services/engine/dantex/knowledge_policy.py.
