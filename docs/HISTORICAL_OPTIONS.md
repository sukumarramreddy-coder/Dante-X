# Historical option research archive

The archive is separate from live validation observations. It does not enable
trading, assign probabilities, or claim that candle-only data reproduces Dante's
live strategy.

## Scope and selection

The initial scope is the existing 90 index sessions, 19 May through 24 September
2026. For NIFTY and BANKNIFTY, select the nearest expiry on or after each session,
the strike closest to the previous completed session's index close, and its
immediate lower and higher strikes, with both calls and puts. This freezes up to
six contracts per index per day without looking at that day's future prices.
It is a research universe, not a reconstruction of the live Greek/quality ranking.
Contracts that expire after the archive end use the current-contract endpoint.

The metadata is retrospective; point-in-time listing availability is not proven.
Selection gaps are reported, not silently replaced by another expiry or strike.

## Storage and validation

`scripts/archive_options.py` takes an index archive, output directory, and local
environment file. Only the read-only Analytics Token is accepted. It permits a
fixed set of market-data GET endpoints and never records credentials.

Raw successful responses are compressed and keyed by request-path hash. These
are reused on a rerun. Failed requests are retried with bounded backoff. The
normalized SQLite archive retains first-seen observations and appends audit
events. Conflicting observations are reported without overwriting old values.
Conflicts within a response are excluded from that response's accepted candles.

Accepted rows require timezone-aware minute timestamps, finite positive OHLC,
valid OHLC geometry, nonnegative volume/OI, the requested date range, and regular
hours of 09:15 through 15:29 IST. Raw rejected rows remain inspectable. A regular
grid has 375 distinct minutes; missing bars may be no-trade minutes or provider
gaps. No price is forward-filled. A quality flag on a request range conservatively
marks its selected contract-days for review. A complete grid alone does not prove
correct prices or profitable execution.

The full manifest includes source index location, daily selections and contract
metadata. Coverage reports enumerate selected contract-days, irregularities and
fetch failures. `local-data/` is ignored by Git. Back up this directory separately.
Do not point these scripts at the live validation database.

## Replay boundary

`scripts/audit_replay.py` joins the archived candles chronologically at exact
timestamps and records the existing decision gate's response to unavailable
evidence. Candle information is marked known only after the minute has closed.
The audit does not fabricate family votes or pass missing data as fresh evidence.
Its blocked decisions are **not a count of missed opportunities or losing trades**.

The current live strategy needs historical bid/ask spreads and Greeks for contract
quality and ranking, plus equivalent historical evidence for its remaining gates.
Candle OHLCV/OI does not provide those fields. Therefore this archive alone cannot
produce a faithful strategy replay, target-before-stop labels for that strategy,
or publishable calibration. Even with valid plans, a candle touching both stop and
target cannot establish which occurred first. Costs, fill assumptions, duplicate
signals and walk-forward validation must also be explicit before any probability.

Finish resolving the 90-session replay requirements before extending the bulk
archive to one year. Once a faithful replay works, freeze the model/selection
policy, use chronological development and validation periods, and reserve a later
period from tuning. Do not use this candle subset to publish the live model's
probability or weaken its readiness gates.
