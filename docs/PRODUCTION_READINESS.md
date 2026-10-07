# Production readiness

“Code complete” and “ready to trust with money” are different states.

The application remains SHADOW until all required gates are satisfied:

1. reliable licensed/live provider connected and freshness monitoring proven
2. historical dataset normalized with survivorship/session/expiry handling
3. walk-forward and out-of-sample validation completed by asset/setup/regime
4. probability calibration meets sample-size and calibration-error requirements
5. realistic brokerage, taxes, spread and slippage included
6. CI and adversarial suites green
7. shadow observation period completed without trigger drift or execution-policy violations

Until then, the terminal may display Live Confirmation, Path Match, Potential Left and opportunity scores. It must not label those values as a win probability.

Dante X remains read-only. Manual broker execution is an intentional boundary.
