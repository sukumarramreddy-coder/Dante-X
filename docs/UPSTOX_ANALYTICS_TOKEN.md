# Upstox Analytics access token

Dante X prefers the Upstox Analytics access token for the read-only provider when the account supports it.

Properties shown by Upstox in the Developer Apps UI:
- long-lived token with one-year validity
- read-only API access
- Market Data and Real-time & Streaming APIs
- no permission to place, modify or cancel orders

Dante X reads this secret only from the runtime environment variable `UPSTOX_ANALYTICS_TOKEN`.

Never commit the token, paste it into an issue/PR/chat, expose it to the browser, or log the Authorization header.

The generic OAuth implementation remains isolated as an optional future authentication mechanism; it is not required for the Analytics-token provider path.
