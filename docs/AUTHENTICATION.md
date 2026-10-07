# Upstox authentication

Dante X uses the standard Upstox OAuth authorization-code flow.

The user authenticates directly with Upstox. Dante X never asks for or stores the user's Upstox password, PIN, TOTP or OTP.

The application constructs the Upstox authorization URL with a CSRF state value. The redirect callback must validate that state before exchanging the short-lived authorization code for an access token.

Client secrets and access tokens are server-side secrets. They must never be committed to GitHub or sent to the browser.

The token exchange is intentionally not activated until the user creates an Upstox API application and supplies its client ID/secret through secure runtime configuration.

At that point the provider can be tested end-to-end in SHADOW mode before any live signal authorization is enabled.
