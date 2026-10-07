# Security boundary

Dante X is a read-only intelligence system.

- Never commit broker/API secrets.
- Never expose provider credentials to the browser.
- Server-side provider tokens are loaded from runtime environment/secret storage.
- Logs redact credentials and should avoid unnecessary account identifiers.
- The engine does not expose order placement, modification, cancellation or fund-transfer methods.
- Live provider permissions should be the minimum read-only scope available.
- Production endpoints require authentication and transport encryption before remote exposure.
- Database backups and audit exports may contain trading history and must be treated as private.
