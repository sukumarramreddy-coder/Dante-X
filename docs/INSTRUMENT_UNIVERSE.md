# Instrument universe

Dante X uses Upstox `instrument_key` as the provider-side canonical identity. Exchange tokens are not persisted as permanent identity because exchanges may reuse them after expiry.

The BOD JSON instrument master is normalized into provider-independent instrument records and classified into cash, futures, options, indices and global-context instruments. Expired derivatives are removed from the active universe.

The master should be refreshed after Upstox publishes its daily BOD file and refreshed again only when the provider signals an intraday instrument change.

Global instruments are context inputs rather than assumed executable Indian contracts. Their published latency metadata must be respected; a delayed global indicator must never be represented as tick-real-time evidence.
