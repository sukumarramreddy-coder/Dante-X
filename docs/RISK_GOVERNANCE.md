# Risk governance

Risk controls sit above signal quality.

- Daily loss limits are circuit breakers, not loss targets.
- Open maximum risk counts against the remaining daily loss budget.
- Profits do not automatically expand the configured daily loss budget.
- Correlated positions share exposure buckets; several bullish index bets are not treated as independent diversification.
- Quantity is determined only after natural structural invalidation and cost assumptions.
- An ARMED trigger is immutable. A different trigger requires explicit cancellation, fresh evidence and a new auditable revision.
- No setup quality score can override a tripped circuit breaker.
