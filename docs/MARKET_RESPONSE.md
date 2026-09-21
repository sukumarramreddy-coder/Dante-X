# Market-response intelligence

Catalysts are hypotheses about what price should do, not commands to the market.

Dante X compares the expected reaction with actual price, breadth and volatility response.

Examples:

- materially negative catalyst + index refuses to fall + breadth improves + volatility fails to rise: bearish thesis is penalized and bullish reversal evidence is strengthened
- materially positive catalyst + index refuses to rise + breadth deteriorates + volatility rises: bullish thesis is penalized and bearish reversal evidence is strengthened

The response engine never authorizes a trade by itself. It adjusts the competing hypotheses, which still must pass structure, path, option-response, liquidity, Potential Left, risk and execution gates.

This is the formal implementation of: price response outranks narrative.
