# Contract selection

Correct market direction does not make every derivative contract executable.

Before a contract can be surfaced, Dante X evaluates bid/ask validity, spread, volume, open interest, expiry risk, remaining potential, Greeks/IV context and estimated execution costs.

Thresholds are asset-class and provider specific in production. Current defaults are conservative scaffolding, not calibrated market constants.

Near expiry, authorization becomes stricter. The final expiry window may block new directional option entries entirely while still allowing management of existing positions.

The terminal must distinguish “thesis valid” from “contract blocked.”
