# Shadow Mode

Shadow Mode is the mandatory bridge between code completion and live decision support.

It consumes timestamped recorded or simulated market events through the same state machine used by live mode, but cannot produce broker orders.

## Goals

- prove ARMED triggers do not drift
- verify cancellation and expiry behavior
- detect stale-data failures
- measure MFE/MAE and realized path quality
- estimate costs/slippage
- expose false confirmation and late-chase behavior
- collect calibration samples

A model is not promoted merely because a backtest looks attractive. Promotion requires out-of-sample and walk-forward evidence, sufficient sample size by instrument/regime, and calibration checks.

Until those conditions are met, UI confidence fields remain Live Confirmation, Path Match and Potential Left—not win probability.
