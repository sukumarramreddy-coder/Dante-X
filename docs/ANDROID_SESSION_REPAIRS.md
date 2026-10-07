# Android 0.4.0 and session-recording repairs

PR #1 / build/foundation. Existing Oct 1 coding workspace retained.

## Behavior

The dashboard presents separate NIFTY and BANK NIFTY cards, each with CE/PE
percentages, provisional/uncalibrated labeling, independent action, and
expandable evidence and blockers. The address editor and /health test live
in Settings, accessible online or offline. Endpoint diagnostics are collapsed.
Saved addresses survive restart; the default is still .109:8000. LAN HTTP and
network permissions are unchanged. Android versionCode 4, versionName 0.4.0.

The engine adds index_probability_reviews.NIFTY and .BANKNIFTY to the current
expert-review response. Each index uses its own structure and option-response
families, with its own freshness gate. The conservative display-only formula is
50 + 15 * (local CE-family count - local PE-family count) / 2. Conflicting or
stale evidence yields an explicitly labeled neutral 50/50 prior. Equal values
can legitimately occur. This is a new engineering heuristic, not a fitted or
calibrated forecast. It never consumes the consolidated percentage or feeds
back into consensus, training admission, risk gates or authorization.

Android rejects expired, future, malformed and wrong-scope directional values.
An older engine lacking the new fields shows an engine-update message rather
than assigning a consolidated value to both indices. Restart-restored engine
context is explicitly stale and neutral. Independent dashboard API requests
run concurrently so endpoint timeouts do not accumulate sequentially.

## Recording fixes

- The observer passes its evaluated payload to learning. Learning does not
  evaluate or persist a second decision for that cycle.
- build_option_duel forwards supplied option snapshots to evaluation rather
  than discarding them and fetching another pair.
- The outcome queue filters eligible DETECTED/ARMED/GO rows before LIMIT.
- Outcome tracking is forward-only from process startup. Existing historical
  records remain untouched; missing historical prices are never invented.
- Forward paths use verified, timestamped option quotes for the selected
  contract and stop at the 30-minute/session-close deadline. Future, stale,
  duplicate and post-deadline observations cannot enter the path.
- Missing or substantially gapped forward observations are censored, not counted
  as wins. Censored new rows leave the pending queue and tracked memory is freed.
- Closing cycles finalize already-observed paths without consuming post-market
  context prices. Censorship does not repair past lost validation evidence.

## Validation and remaining limits

Engine regression tests cover single evaluation per observer cycle, input
identity, SQL queue eligibility, preservation of pre-start rows, bounded forward
paths, incomplete-path censorship, per-index divergence, freshness isolation,
and stale/restart handling. Android tests cover separate percentages, missing
schema, timestamps, scope, neutral priors, persistence and LAN requests.

Emulator checks use a synthetic local feed (NIFTY 65/35, BANK NIFTY 35/65) solely
to verify layout and routing. They are not market predictions. Settings and
saved-address persistence were exercised in the installed APK.

No validation reset, historical relabeling, token change or live execution is
part of this patch. Verified Greeks, missing index VWAP volume, validated
structural plans and empirical calibration remain separate unresolved inputs;
no substitutes were manufactured. Physical-phone installation and the next
live market session remain user-side verification steps.
