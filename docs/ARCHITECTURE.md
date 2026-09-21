# Dante X Architecture

## Design law

**Price response > structure > breadth/related markets > option response > derivatives > news thesis.**

News describes pressure. Price response tells us whether that pressure is being accepted, absorbed, or reversed.

## Pipeline

1. **Provider layer** normalizes read-only ticks, candles, futures, options, volatility, breadth, sector and event data.
2. **Feature engines** compute structure, VWAP/opening range, momentum, displacement, volume/liquidity, relative strength, options/Greeks/IV/OI and catalyst response.
3. **Hypothesis engine** maintains bullish and bearish hypotheses simultaneously.
4. **Authorization engine** rejects correlated pseudo-confirmation and poor execution quality.
5. **Risk engine** determines natural invalidation first and quantity last.
6. **Radar** ranks executable asymmetries across the approved universe.
7. **Focus** produces the exact contract/trigger/entry/stop/targets/cancel condition.
8. **Audit/validation** stores every state change and evaluates MFE, MAE, costs and calibration.

## Asset-class awareness

The common signal contract is universal, but features and calibration are modelled separately for:
- index/index options
- equity/equity options
- currency/currency options

A NIFTY weekly option and USDINR are not scored as though they share identical microstructure.

## Signal authorization

A setup must pass:
- liquidity and spread quality
- structural location and natural invalidation
- independent evidence (not duplicated correlated indicators)
- positive net reward/risk after estimated costs/slippage
- remaining potential
- horizon classification before entry

No valid asymmetry means **NO EDGE**.

## Trigger immutability

Once a setup reaches ARMED, its trigger is not moved merely because price approaches it. New evidence may explicitly CANCEL it; otherwise it fires or expires.

## Probability policy

Live Confirmation, Path Match and Potential Left are deterministic scores. They are not probabilities.

A probability field becomes available only after:
- sufficient historical samples,
- walk-forward/out-of-sample testing,
- calibration by probability band,
- regime and instrument-family checks,
- net-of-cost evaluation.

Until then the API must return probability as unavailable.
