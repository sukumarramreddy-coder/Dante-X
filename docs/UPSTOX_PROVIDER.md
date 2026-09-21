# Upstox provider

Upstox is the first production-data adapter target.

Implemented REST surfaces:
- V3 historical candles
- V3 intraday candles
- V2 put/call option chain
- V3 market-feed authorization

The live V3 WebSocket transport is the next provider component. Its Protobuf payload is normalized before entering Dante X; provider-specific objects must not leak into decision logic.

The provider remains read-only. No order endpoints are implemented.

## Authentication

The access token is supplied at runtime only. Never commit it, paste it into source code, or expose it to the web client.

## Validation

Live promotion still requires provider freshness/reconnect tests plus historical walk-forward validation. A connected feed does not by itself make probability calibration valid.
