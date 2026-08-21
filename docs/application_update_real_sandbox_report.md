# OAS-K Real Application Sandbox Test

## Executive Summary

Real application sandbox testing completed in `D:\OAS-K_Real_Application_Sandbox` using real PyInstaller OAS-K builds and the real standalone updater EXE.

Final decision: `READY_FOR_RESTRICTED_ENVIRONMENT_TEST`.

This decision means the update flow is ready for a controlled restricted-environment test. It does not mean it is ready to run directly on an office workstation or production Data Root.

## Build Audit

- Branch: `agent/improve-automation-workflows`
- HEAD: `33d32617a0fd945641eda9547003178e198eee75`
- Entry point: `main.py`
- Spec file: `OAS-K.spec`
- Build mode: PyInstaller onefile
- Active source version after test: `1.0.0`
- Updater EXE: `D:\Python Project\OfficeAutomationSuite-Karina\dist\updater\OAS-K-Updater.exe`
- Updater SHA256: `83F28E854BA232178431FD3B47432110766B7F87588AE27B6B1A953A0D206907`

Baseline source validation before real sandbox execution:

- `py -m pytest tests\update -v`: `43 passed, 1 warning in 4.19s`
- `git diff --check`: passed, with only Git line-ending warnings

Built baseline application:

- Version: `1.0.0-sandbox`
- Path: `D:\OAS-K_Real_Application_Sandbox\Artifacts\OAS-K_1.0.0-sandbox\OAS-K.exe`
- Size: `73082490`
- SHA256: `894249939cc60475a3758911655fb25f9d8d1414451a9e0ecd5079765544ba33`

Built target application:

- Version: `1.0.1-sandbox`
- Path: `D:\OAS-K_Real_Application_Sandbox\Artifacts\OAS-K_1.0.1-sandbox\OAS-K.exe`
- Size: `73082432`
- SHA256: `32ffadc6f9e60a97b2c2033a8e8d129dcac62f3354b34ef3d0889b73a053f726`

The actual build output contains only `OAS-K.exe` because the existing project spec produces a onefile executable. Assets, fonts, icons, and runtime resources are embedded by PyInstaller rather than copied as standalone folders.

## Dummy Data Root

The test used an isolated Data Root:

- Data Root: `D:\OAS-K_Real_Application_Sandbox\Data`
- Database: `D:\OAS-K_Real_Application_Sandbox\Data\database\OAS-K.db`
- Recorder profile: `D:\OAS-K_Real_Application_Sandbox\Data\recorder_profiles\hris\sandbox_profile.json`

The office app folder, production Data Root, and production database were not used as the application root or test data source.

## Package Build

The official package builder was used:

- Tool: `tools\build_update_package.py`
- Help command: `py tools\build_update_package.py --help`
- Package output root: `D:\OAS-K_Real_Application_Sandbox\Packages`

Happy-path package:

- Path: `D:\OAS-K_Real_Application_Sandbox\Packages\OAS-K_Update_v1.0.1-sandbox.zip`
- SHA256: `165bec11b6253869368a51fa18cdcb091561fd7a09c50b71364d07c50f384c9a`
- Validation: valid
- Contents: `application/`, `application/OAS-K.exe`, `checksums.sha256`, `manifest.json`, `release_notes.txt`

Rollback-path package:

- Path: `D:\OAS-K_Real_Application_Sandbox\Packages\OAS-K_Update_v1.0.2-sandbox.zip`
- SHA256: `aef0ec56b592c028b9afe4ca354a2c66874c5812303a3430b26f0e44c8d299ce`
- Validation: valid
- Failure method: package manifest declared `1.0.2-sandbox` while the staged executable was actually `1.0.1-sandbox`, causing health-check version mismatch after replacement.

## Happy Path

- Transaction ID: `9f8128b1-8d19-4db2-9173-e379c98023fd`
- Updater exit code: `0`
- Final transaction status: `SUCCESS`
- New process ID: `24600`
- Started: `2026-07-30T13:05:01`
- Finished: `2026-07-30T13:05:07`

Transaction timeline:

```text
STAGED
APPLY_REQUESTED
WAITING_FOR_SHUTDOWN
BACKING_UP_APPLICATION
APPLYING
APPLICATION_REPLACED
STARTING_NEW_APPLICATION
HEALTHCHECK_PENDING
SUCCESS
```

Result:

- Active executable SHA256 after update matched target build SHA256.
- Health marker was created.
- Health check reported application version `1.0.1-sandbox`.
- Health check passed `application_root`, `application_version`, `data_root`, `database_open`, `logger_write`, `schema_compatible`, and `ui_shell_created`.
- Rollback backup existed after success.

Data Root integrity after happy path:

- Database SHA256 before and after: `e2380b6424bffbcb3ccf9839bb028424ec07e5d12253ea924f451222b90019b3`
- Recorder profile SHA256 before and after: `6989b8165b42ccf4534a4b2e3d360165e87125c591b6299c34a365c5bfb84dba`

## Rollback Path

- Transaction ID: `362ed15d-8ec2-42ec-9264-f8bd42968e63`
- Updater exit code: `16`
- Final transaction status: `ROLLED_BACK`
- Last error: `Health check failed or timed out.`
- Started: `2026-07-30T13:05:30`
- Finished: `2026-07-30T13:06:04`

Transaction timeline:

```text
STAGED
APPLY_REQUESTED
WAITING_FOR_SHUTDOWN
BACKING_UP_APPLICATION
APPLYING
APPLICATION_REPLACED
STARTING_NEW_APPLICATION
HEALTHCHECK_PENDING
ROLLBACK_REQUESTED
ROLLBACK_IN_PROGRESS
ROLLED_BACK
```

Result:

- Active executable SHA256 after rollback matched baseline build SHA256.
- Failed application diagnostics were retained at `D:\OAS-K_Real_Application_Sandbox\Data\update\failed\362ed15d-8ec2-42ec-9264-f8bd42968e63\application`.
- Rollback backup still existed after rollback.

Data Root integrity after rollback path:

- Database SHA256 before and after: `bfad8310915ff17ad5f2319c0d5730fbffa2b7b6677e78fd5a21e90b692c795a`
- Recorder profile SHA256 before and after: `6989b8165b42ccf4534a4b2e3d360165e87125c591b6299c34a365c5bfb84dba`

## Restricted-Access Test

The updater was run from a regular shell without requesting elevation.

- UAC prompt observed: no
- Permission denied observed: no
- Internet required during apply: no
- Antivirus quarantine observed: no
- SmartScreen block observed: no
- Antivirus disabled: no

This confirms the sandbox update flow can execute under normal user context for the tested folder layout.

## Registry Safety

The test used the real HKCU storage registry because the application health check reads the configured Data Root from that registry.

Registry values before test:

- Data Root: `D:\OAS-K-Data`
- Database path: `D:\OAS-K-Data\database\OAS-K.db`

Registry values during test:

- Data Root: `D:\OAS-K_Real_Application_Sandbox\Data`
- Database path: `D:\OAS-K_Real_Application_Sandbox\Data\database\OAS-K.db`

Registry values were restored after test:

- Data Root: `D:\OAS-K-Data`
- Database path: `D:\OAS-K-Data\database\OAS-K.db`
- Restoration status: restored and verified

Registry event details are stored at `D:\OAS-K_Real_Application_Sandbox\Reports\registry_events.json`.

## Regression Tests

Post-simulation update tests:

- Command: `py -m pytest tests\update -v`
- Result: `43 passed, 1 warning in 27.77s`

Post-simulation full regression:

- Command: `py -m pytest`
- Result: `699 passed, 2 skipped, 1 warning in 88.76s`

The warning is expected from the duplicate zip path validator test. That test intentionally constructs a duplicate path package and verifies the validator rejects it.

## Risks and Limitations

The first real-app attempt exposed a harness issue with PyInstaller onefile parent processes. The process ID returned by the harness was not equivalent to the in-app process ID that the GUI would pass to the updater. This caused a locked `OAS-K.exe` during replacement.

That attempt was not counted as a pass. The scenario was corrected by launching the real old app, verifying it stayed running, then closing all sandbox OAS-K processes before invoking the updater. This better represents the GUI close-and-apply sequence where the app closes itself before the external updater replaces the executable.

The test proves real build replacement and rollback in an isolated sandbox. It does not yet prove behavior on a restricted office workstation with live endpoint security policy, network drive restrictions, or production user data.

## Final Decision

`READY_FOR_RESTRICTED_ENVIRONMENT_TEST`

Recommended next step: run the same controlled flow in a restricted environment using a dummy Data Root and dummy application folder first. Do not run against the office application folder or production Data Root until that restricted dummy test passes.
