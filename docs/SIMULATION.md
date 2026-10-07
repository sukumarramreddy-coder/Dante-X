# Artificial session simulation

The simulator exists to catch behavioral defects before real market data is connected.

Scenarios should include:

- trigger approached but never touched
- exact trigger fire
- gap through trigger
- cancellation before trigger
- expiry unused
- target then reversal
- stop immediately after entry
- underlying confirms while option fails
- option spikes without underlying confirmation
- late-session setup that must be blocked
- high-probability-looking but spent move
- trend, range, volatile and compression regimes

Simulation is not evidence of profitability. It verifies system behavior. Profitability claims require historical, out-of-sample, walk-forward validation with realistic costs and slippage.
