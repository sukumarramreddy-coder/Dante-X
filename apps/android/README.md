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

    http://192.168.1.109:8000/

`10.0.2.2` can be entered for the Android emulator to reach the Windows host.

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

Version 0.4 shows two separate NIFTY and BANK NIFTY cards. Each consumes its
own `index_probability_reviews` entry from `/v1/decision/current`. The server
uses that index's structure and option-response families for a bounded,
provisional directional prior. Shared consensus and trade authorization remain
independent. Equal values are possible when evidence agrees or is neutral.

The screen shows provisional CE/PE percentages, CE/PE action and expandable
evidence/blockers. Technical endpoint diagnostics are collapsed. The URL editor
and health test are available through Settings, including while offline. The
saved address survives restart. The default remains http://192.168.1.109:8000/.

Missing per-index API fields never fall back to the consolidated probability.
The app requests an engine update instead. Expired, future-dated, wrong-scope
or malformed values display Unavailable. Explicit 50/50 neutral priors remain
labeled. No calibrated win-rate or profit claim is made.

Run `gradlew testDebugUnitTest assembleDebug lintDebug`. Debug builds are signed
with the local Android debug certificate. No network permissions were added;
existing LAN HTTP support is retained. Phone installation is a manual step.
