# Live provider lifecycle

The provider state machine is:

OFFLINE -> CONNECTING -> SYNCING -> LIVE -> STALE/RECONNECTING -> SYNCING -> LIVE.

Dante X cannot authorize a signal merely because a WebSocket is open. The feed must have completed the provider's initialization sequence and the instrument-specific tick must still be fresh.

A stale feed immediately blocks new signal authorization. After reconnect, the old synchronization state is not reused; a fresh market-status/snapshot sequence is required.

This prevents stale prices from silently becoming exact ARMED/GO triggers.
