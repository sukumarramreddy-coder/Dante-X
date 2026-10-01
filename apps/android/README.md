# Dante-X Android Console

Read-only Android operator console for the Dante-X shadow engine.

Backend baseline:

    PR #1 build/foundation — additive probability_review contract

The Android application:

- does not place broker orders
- does not modify broker orders
- does not cancel broker orders
- does not calculate calibrated probabilities independently
- does not bypass backend freshness/risk/calibration gates
- displays backend state only

Default debug backend:

    http://10.0.2.2:8000/

`10.0.2.2` maps the Android emulator to the Windows host.

For a physical phone, use the laptop LAN IP while both devices are on the
same trusted network. Do not expose the development API directly to the
public Internet.

Backend endpoints consumed:

- /health
- /v1/decision/current
- /v1/calibration/learning
- /v1/expert/status
- /v1/signals

Additional backend endpoints remain available for later screens.

Version 0.2 displays the backend's shared NIFTY directional preference with
BANKNIFTY confirmation, separately from final action and paper lifecycle.
It consumes `/v1/decision/current.probability_review`; it never reads model
advice as calibrated profit odds or invents per-index percentages. Four-way
per-index evidence scores and missing/stale reasons are displayed separately.
Malformed or expired directional values display Unavailable; a backend neutral
prior is explicitly labeled. All values use percent units, including values
below 1, without implicit rescaling.

Run `gradlew testDebugUnitTest assembleDebug`. The debug APK uses the existing
trusted-LAN backend address in app/build.gradle.kts. Phone installation requires
an attached authorized device or manually installing the APK. No broker
execution is implemented. Local SDK paths and build caches are excluded.
