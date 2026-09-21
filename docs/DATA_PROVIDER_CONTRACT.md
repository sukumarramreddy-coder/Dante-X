# Read-only Data Provider Contract

Dante X never requires order placement credentials.

A production provider adapter must normalize exchange timestamps, instrument identity, LTP/bid/ask/spread/depth, OHLCV candles, futures price/basis/OI, option-chain strikes and expiries, CE/PE premiums, volume, OI/change, IV/Greeks, volatility index, breadth inputs, and trading-session metadata.

## Provider health

Every event carries a timestamp. The engine rejects stale execution data rather than silently treating it as current.

## Secret policy

Credentials are runtime secrets. They are never stored in Git, signal logs, browser payloads or screenshots.

## Execution boundary

Provider adapters expose reads and streams only. Order placement, order modification, order cancellation and fund-transfer interfaces do not belong in Dante X.
