# OAS-K Restricted Environment Test Report

## 1. Executive Summary

- Date/time: 2026-07-30, Asia/Bangkok
- Windows: Windows 10 Home Single Language, version 2009, build 26200, 64-bit
- Username: `desktop-uhciihs\user`
- Token: standard / non-elevated token (`Medium Mandatory Level`; Administrators group present as deny-only)
- Branch: `agent/improve-automation-workflows`
- Commit: `33d32617a0fd945641eda9547003178e198eee75`
- Baseline version: `1.0.0-sandbox`
- Target version: `1.0.1-sandbox`
- Updater SHA-256: `83f28e854ba232178431fd3b47432110766b7f87588ae27b6b1a953a0d206907`
- Happy package SHA-256: `165bec11b6253869368a51fa18cdcb091561fd7a09c50b71364d07c50f384c9a`
- Rollback package SHA-256: `aef0ec56b592c028b9afe4ca354a2c66874c5812303a3430b26f0e44c8d299ce`
- Sandbox root: `D:\OAS-K_Restricted_Environment_Test`
- Overall result: `NOT_READY`

The restricted test proved non-admin real EXE startup, local package validation, local application replacement, health-check success, rollback success, Data Root preservation, Defender active state, and HKCU registry restoration. It did not prove true offline apply because GitHub remained reachable, VS Code was still open, the happy-path updater process exit code was not captured due the launcher wait wrapper staying attached while the new app remained alive, and the full GUI user workflow was not executed end to end.

## 2. Environment Restrictions

- Non-admin execution: verified by `whoami /groups`; token was medium integrity.
- Python absence during runtime apply: updater apply was executed by `OAS-K-Updater.exe`; Python was used for tester-side setup, package validation, staging, and report generation.
- VS Code closed: failed. `Get-Process Code` showed active VS Code processes.
- Antivirus state: Microsoft Defender and Windows Security were active.
- Internet/offline state: failed. `Test-NetConnection github.com -Port 443` returned `TcpTestSucceeded: true`.
- Application Root permission: pass for create, read, rename, and delete of a temporary file under `D:\OAS-K_Restricted_Environment_Test\Application`.
- Data Root permission: pass through schema creation, pre-update backup, staging, logs, rollback, failed diagnostics, and health marker writes.
- Registry scope: HKCU only. HKLM was not touched.

## 3. Runtime Independence

- OAS-K startup without source execution: pass. `OAS-K.exe` was launched from `D:\OAS-K_Restricted_Environment_Test\Application`.
- Startup observation: after 12 seconds, sandbox OAS-K processes were still running from the sandbox Application Root.
- Updater startup without source execution: pass. `OAS-K-Updater.exe --help` worked from `D:\OAS-K_Restricted_Environment_Test\Data\update\runtime\restricted-test`.
- Missing Python runtime error: not observed.
- Missing DLL/Tcl/Tk/assets/font/icon error: not observed during process startup.
- PyInstaller behavior: onefile application build. The executable spawns more than one OAS-K process, consistent with the previous real sandbox finding.

## 4. Offline Package Validation

- Happy package: `D:\OAS-K_Restricted_Environment_Test\Packages\OAS-K_Update_v1.0.1-sandbox.zip`
- Failure package: `D:\OAS-K_Restricted_Environment_Test\Packages\OAS-K_Update_v1.0.2-sandbox.zip`
- Validator result: both valid.
- Network request by validator: none observed or required by implementation.
- Offline result: not proven. Internet was still reachable when checked.

## 5. Happy Path

Steps actually executed:

1. Copied baseline `OAS-K.exe` into restricted sandbox Application Root.
2. Created dummy Data Root and dummy database using the official schema initializer.
3. Wrote a dummy HRIS recorder profile.
4. Temporarily pointed HKCU storage registry to sandbox Data Root.
5. Validated local update package.
6. Prepared update, including database backup and staging.
7. Ran sandbox `OAS-K-Updater.exe`.
8. Verified transaction, health marker, executable hash, backup, rollback copy, and Data Root hashes.

- Transaction ID: `84142ebf-e8d1-4196-adae-f0111a16526e`
- Status timeline: `APPLY_REQUESTED -> WAITING_FOR_SHUTDOWN -> BACKING_UP_APPLICATION -> APPLYING -> APPLICATION_REPLACED -> STARTING_NEW_APPLICATION -> HEALTHCHECK_PENDING -> SUCCESS`
- Updater exit code: not captured. The updater completed successfully, but the `Start-Process -Wait` wrapper did not return before timeout because the new OAS-K process remained alive.
- Application version before: `1.0.0-sandbox`
- Application version after: `1.0.1-sandbox`
- Health-check: pass, including `application_root`, `application_version`, `data_root`, `database_open`, `logger_write`, `schema_compatible`, and `ui_shell_created`.
- Database backup: `D:\OAS-K_Restricted_Environment_Test\Data\backup\database\OAS-K_2026-07-30_132309.db`
- Rollback copy: `D:\OAS-K_Restricted_Environment_Test\Data\update\rollback\84142ebf-e8d1-4196-adae-f0111a16526e`
- Application hash after happy path: `32ffadc6f9e60a97b2c2033a8e8d129dcac62f3354b34ef3d0889b73a053f726`
- Database hash before/after: `ec04688e4b1d4f32af4939bb7ca18c8cd8fd25255c9097886504cc14978d0dd0`
- Recorder profile hash before/after: `e5d8f091a701b42a7bb6c87bad2568a94d1e66f6eaa7cdb2dbf024ac7ba53eaf`
- UAC/permission result: no elevation prompt or permission denied observed.
- Antivirus/SmartScreen result: no hard-block or quarantine observed.

Acceptance status: not a full PASS because offline state, GUI workflow, VS Code closure, and happy updater exit-code capture were not fully satisfied.

## 6. Rollback Path

- Failure method: manifest target version `1.0.2-sandbox` while the staged executable reports `1.0.1-sandbox`, causing controlled health-check version mismatch.
- Transaction ID: `7196ef9b-9299-4a57-8ac7-32b43237c157`
- Status timeline: `APPLY_REQUESTED -> WAITING_FOR_SHUTDOWN -> BACKING_UP_APPLICATION -> APPLYING -> APPLICATION_REPLACED -> STARTING_NEW_APPLICATION -> HEALTHCHECK_PENDING -> ROLLBACK_REQUESTED -> ROLLBACK_IN_PROGRESS -> ROLLED_BACK`
- Updater exit code: `16`
- Restored application version: baseline `1.0.0-sandbox`
- Restored executable SHA-256: `894249939cc60475a3758911655fb25f9d8d1414451a9e0ecd5079765544ba33`
- Health-check failure: `Health check failed or timed out.`
- Failed diagnostics: `D:\OAS-K_Restricted_Environment_Test\Data\update\failed\7196ef9b-9299-4a57-8ac7-32b43237c157\application`
- Database hash before/after: `ec04688e4b1d4f32af4939bb7ca18c8cd8fd25255c9097886504cc14978d0dd0`
- Recorder profile hash before/after: `e5d8f091a701b42a7bb6c87bad2568a94d1e66f6eaa7cdb2dbf024ac7ba53eaf`
- Antivirus result: no hard-block or quarantine observed.

Acceptance status: rollback mechanics PASS, but offline rollback was not proven.

## 7. Registry Safety

- Key: `HKCU\Software\OTO Finance\OAS-K`
- Values: `DataRoot`, `DatabasePath`
- Initial state:
  - `DataRoot`: `D:\OAS-K-Data`
  - `DatabasePath`: `D:\OAS-K-Data\database\OAS-K.db`
- Test state:
  - `DataRoot`: `D:\OAS-K_Restricted_Environment_Test\Data`
  - `DatabasePath`: `D:\OAS-K_Restricted_Environment_Test\Data\database\OAS-K.db`
- Restored state:
  - `DataRoot`: `D:\OAS-K-Data`
  - `DatabasePath`: `D:\OAS-K-Data\database\OAS-K.db`
- Restore verification: pass.

## 8. Security and Antivirus Observations

- SmartScreen: no prompt observed in this run.
- Defender: active.
- Real-time protection: active.
- Tamper protection: active.
- Quarantine: none observed.
- Warning dialog: none observed.
- Corporate policy limitation: not simulated.
- Code-signing limitation: application/updater are not confirmed code-signed here, so SmartScreen behavior may differ on office machines.

## 9. User Workflow

The intended user workflow is browser download plus OAS-K GUI: select package, validate, prepare, close and apply, then wait for app restart.

This test did not execute the full GUI workflow end to end. Tester-side terminal/Python was still required for staging and transaction setup. Therefore the office-user workflow is not fully proven yet.

## 10. Recovery Kit

Path: `D:\OAS-K_Restricted_Environment_Test\RecoveryKit`

Contents created:

- `README_RECOVERY.txt`
- `registry_before.json`
- baseline application SHA-256
- package SHA-256 values
- updater SHA-256
- rollback folder paths
- registry restore information
- manual Application Root recovery steps
- updater log location
- office pilot cancellation steps
- list of files that must not be deleted

## 11. Regression Tests

Commands and results:

- `git diff --check`: exit code 0; only Git LF-to-CRLF working-copy warnings.
- `py -m pytest tests\update -v`: `43 passed, 1 warning in 4.85s`.
- `py -m pytest`: `700 passed, 1 skipped, 1 warning in 68.72s`.

The warning is the intentional duplicate ZIP path validator test.

## 12. Risks and Limitations

- Not code signed.
- SmartScreen may differ on an office computer.
- Corporate antivirus policy was not fully simulated.
- Application Root must be writable by the standard user.
- Update is application-only.
- No database migration is enabled.
- Production data was not used.
- Main office installation was not tested.
- Power loss was not tested.
- Windows logout/shutdown during update was not tested.
- Office pilot must have backup and manual rollback ready.
- True offline apply was not proven in this run.
- VS Code was still open during the test environment audit.
- Full GUI workflow was not proven end to end.
- Happy-path updater exit code was not captured by the first process wrapper, although the transaction and log reached `SUCCESS`.

## 13. Final Decision

`NOT_READY`

Reason: strict `READY_FOR_OFFICE_PILOT` criteria require offline apply PASS, Python-independent GUI workflow PASS, VS Code closed, captured happy-path updater exit code, and no terminal requirement for normal user flow. Those were not fully proven in this run.

## 14. Recommended Office Pilot

Not applicable until blockers are resolved.

Before re-running for `READY_FOR_OFFICE_PILOT`, use one controlled laptop session with:

- VS Code closed.
- Internet actually disabled through Windows UI or disconnected network.
- OAS-K GUI used for validate, prepare, and close-and-apply.
- One local package ZIP.
- Dummy Data Root first.
- No Attendance, Outlook Revisi, HRIS, or Utilities engine execution.
- Manual backup and rollback kit ready.
- One operator observing startup and Settings only.
