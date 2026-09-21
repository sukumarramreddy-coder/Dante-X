# Operations

## Start state

The safe default is SHADOW. A missing environment variable never silently enables live mode.

## Health

Operators should monitor provider freshness, websocket reconnects, clock drift, event backlog, database writes and API/UI health.

## Failure behavior

Provider stale -> NO EDGE.
Provider disconnected -> NO EDGE.
Incomplete option chain -> affected contract blocked.
Audit persistence failure -> signal authorization should fail closed in production.
Risk circuit tripped -> no new setup regardless of score.
UI disconnected -> show OFFLINE, never stale sample data as live.

## Recovery

After a provider reconnect, require fresh snapshots before resuming authorization. Do not replay old triggers as though they are current.
