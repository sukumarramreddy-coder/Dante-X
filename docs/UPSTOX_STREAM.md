# Upstox V3 live stream

The transport follows the current Upstox V3 contract:

1. obtain the authorized market-feed URL using the REST authorization endpoint
2. connect to the returned WebSocket URL
3. send subscription requests as binary messages
4. decode incoming binary Protobuf messages with the official Market Data V3 schema
5. require the initial market-status message and subsequent market snapshot before declaring the feed synchronized
6. monitor freshness continuously; stale/disconnected feeds fail closed
7. reconnect with bounded exponential backoff and require a fresh synchronization sequence after reconnect

Supported subscription modes are `ltpc`, `option_greeks`, `full`, and `full_d30`. Dante X will normally use targeted `full` subscriptions for Focus/Live Trade and cheaper modes for broader Radar coverage.

The official feed limits must be respected by the subscription planner. The engine must not assume every instrument can be subscribed in full mode simultaneously.

The Protobuf decoder is injected into the transport so provider schema generation remains isolated from Dante's decision engine.
