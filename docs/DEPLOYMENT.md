# Deployment

Dante X engine is containerized and defaults to SHADOW mode.

Required runtime secret for the preferred Upstox read-only path:

`UPSTOX_ANALYTICS_TOKEN`

Do not put the token in Dockerfile, docker-compose files, GitHub Actions, source code, screenshots, chat, or browser-side environment variables.

The deployment target must support server-side secret/environment configuration and persistent storage for audit/calibration data.

## Promotion rule

Initial deployment stays `DANTEX_MODE=shadow`. A live provider connection is used to collect/validate data and exercise the full pipeline without presenting unvalidated model scores as calibrated probabilities.

Production signal authorization remains disabled until:
1. live provider freshness/reconnect tests pass,
2. historical walk-forward validation is complete,
3. calibration is publishable,
4. CI is green,
5. the audit store is persistent and fail-closed.

Deployment is not equivalent to model validation.
