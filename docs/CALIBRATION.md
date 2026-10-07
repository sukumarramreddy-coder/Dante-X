# Probability Calibration

Dante X does not equate a model score with probability.

For each instrument family, horizon, regime and setup family, completed shadow/live-observation signals are grouped into score bands. We measure whether the defined target was reached before the structural stop, net of the exact setup definition.

A band must meet a minimum sample requirement before it can even be considered publishable. Publication additionally requires out-of-sample/walk-forward stability, acceptable calibration error, and net-of-cost usefulness.

Example: if signals displayed in a 70–79 score band reach target-before-stop only 54% of the time, Dante X must not label them “70% probability.”

Calibration is versioned. A material model change invalidates stale calibration until revalidated.

The current band helper reports descriptive counts and observed rates only;
`publishable` remains false regardless of sample count. No archive, synthetic
sample, diagnostic heartbeat, or temporary SQLite write can unlock publication.
