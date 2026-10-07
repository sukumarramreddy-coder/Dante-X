# Android engine connection patch (0.3.0)

Implemented in the existing Oct 1 coding workspace on PR #1 / build/foundation,
starting from 66a8b6a. No new repository or branch was created.

## Changes

- Default root address is http://192.168.1.109:8000/ (versionCode 3).
- Engine / API Base URL is editable even while loading or offline.
- Save & Connect validates and stores the normalized HTTP(S) root in private
  Android SharedPreferences. Restarting the app reuses that address.
- Credentials, non-root paths, queries, fragments and invalid ports are rejected.
  Invalid edits or failed persistence cannot replace the last saved setting.
- Test Connection GETs the entered root's /health without persisting it and
  reports backend status, malformed response, HTTP failures or network failures.
- Retrofit clients use the saved address. Each dashboard snapshot captures one
  client for all seven GET endpoints. Saving cancels old polling and clears the
  old dashboard before reconnecting; cancellation is not swallowed.
- Existing LAN cleartext configuration remains unchanged. No new network
  permissions, certificate exceptions or broker/execution endpoints were added.
- Existing provisional CE/PE display remains integrated: UNCALIBRATED values
  render independently from NO_EDGE/WAIT; neutral priors are labeled, stale or
  malformed values remain unavailable. Authorization logic is unchanged.

## Verification

- 320 engine tests passed using temporary test data.
- 8 Android unit tests passed, covering URL validation, persisted-store reload,
  invalid/failed edits, all seven API routes and address switching, provisional
  probability rendering, stale/malformed values and the read-only contract.
- Debug APK assembly passed; Android lint: zero errors, nine existing dependency
  and target-SDK warnings.
- APK signature verified with the existing Android debug certificate. Package
  com.dantex.console, versionName 0.3.0, versionCode 3, minSdk 26.
- Manifest retains INTERNET and AndroidX's generated non-exported receiver
  permission; no added network permission.
- A read-only request to .109:8000/health succeeds and reports service
  dante-x-engine, status degraded. Reachability does not imply trading readiness.

## Preserved state and remaining verification

Validation SQLite was not edited, reset or deleted. Engine source and live
execution configuration were not changed. No engine restart or token change was
performed. Phone installation, visual layout and actual app restart persistence
on a physical device still require verification. Automated persistence tests use
an injected durable-store stand-in; production storage is SharedPreferences.

Install the APK, leave or save http://192.168.1.109:8000, then tap Test Connection.
When DHCP changes the laptop address, edit this setting and Save & Connect;
a new APK is unnecessary. Test Connection checks an unsaved draft without
changing the active dashboard address.
