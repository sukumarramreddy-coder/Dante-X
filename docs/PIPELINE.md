# End-to-end decision pipeline

The shadow/live-observation path is intentionally ordered:

1. ingest normalized timestamped market observation
2. reject stale/incomplete data
3. enforce session and declared horizon
4. generate independent evidence families
5. score bullish and bearish hypotheses
6. compare expected catalyst response with actual market response
7. assess underlying/option confirmation or divergence
8. reject poor liquidity, spread, remaining potential or net R:R
9. generate exact trigger, entry, structural stop, targets and cancellation
10. size quantity only after natural invalidation exists
11. transition to ARMED
12. fire GO only at the immutable trigger, or CANCEL/expire
13. measure path, MFE, MAE, target-before-stop, costs and slippage
14. persist the complete audit record
15. feed completed samples to the calibration laboratory

No language-model narrative may bypass an earlier deterministic gate.
