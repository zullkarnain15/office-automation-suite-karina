# Application Update Sprint 2 Simulation Report

## 1. Executive Summary

- Date/time: 2026-07-30, simulation run around 12:42-12:43 local time.
- Branch: `agent/improve-automation-workflows`
- HEAD: `33d32617a0fd945641eda9547003178e198eee75`
- Working tree state: local Sprint 2 changes are uncommitted; simulation artifacts stayed outside the repository.
- Updater path: `D:\Python Project\OfficeAutomationSuite-Karina\dist\updater\OAS-K-Updater.exe`
- Updater SHA-256: `83F28E854BA232178431FD3B47432110766B7F87588AE27B6B1A953A0D206907`
- Simulation root: `D:\OAS-K_Update_Simulation`
- Overall result: happy path passed, rollback path passed, Data Root integrity passed, full regression passed.

Final decision: `READY_FOR_REAL_APPLICATION_SANDBOX_TEST`

## 2. Audited Implementation

Updater CLI:

```text
OAS-K-Updater.exe --transaction TRANSACTION
                  [--wait-pid WAIT_PID]
                  [--shutdown-timeout SHUTDOWN_TIMEOUT]
                  [--health-timeout HEALTH_TIMEOUT]
                  [--log-path LOG_PATH]
                  [--python-executable PYTHON_EXECUTABLE]
```

Transaction model fields include:

```text
transaction_id, status, current_version, target_version, package_path,
package_sha256, staging_path, staged_application_path, application_root,
rollback_path, database_backup_path, entry_executable, source_process_id,
new_process_id, created_at, updated_at, last_error, log_path
```

Statuses:

```text
STAGED, APPLY_REQUESTED, WAITING_FOR_SHUTDOWN, BACKING_UP_APPLICATION,
APPLYING, APPLICATION_REPLACED, STARTING_NEW_APPLICATION,
HEALTHCHECK_PENDING, SUCCESS, ROLLBACK_REQUESTED, ROLLBACK_IN_PROGRESS,
ROLLED_BACK, FAILED, CANCELLED
```

Health-check marker: `healthcheck_success.json` next to `transaction.json`, with transaction ID, status, application version, database schema version, checked timestamp, and boolean checks.

Post-update argument: `--post-update --update-transaction <transaction.json>`

Post-rollback argument: `--post-rollback --update-transaction <transaction.json>`

Default updater timeouts:

```text
shutdown timeout: 60 seconds
health timeout: 90 seconds
```

Simulation used shorter explicit timeouts: 15 seconds shutdown, 10 seconds happy health, 5 seconds rollback health.

Rollback location: `<DataRoot>\update\rollback\<transaction_id>\application`

Staging location: `<DataRoot>\update\staging\v<version>\application`

Update log location: `<DataRoot>\update\logs\update_<transaction_id>.log`

Updater target version source: `target_version` field in `transaction.json`.

New executable verification: updater checks `<staged_application_path>\<entry_executable>` before replacement and `<application_root>\<entry_executable>` after rollback/restore operations.

Graceful process wait: updater waits for `--wait-pid` using `updater.process_waiter.wait_for_exit`; no force-kill is used.

Exit codes:

```text
0  success
10 invalid transaction
11 old process timeout
12 application backup failed
13 replacement failed
14 new application launch failed
15 health check failed
16 rollback succeeded after update failure
17 rollback failed
18 unexpected error
```

## 3. Safety Controls

- Simulation root guard rejected project root, production-like Data Root, and drive root.
- Simulation used `D:\OAS-K_Update_Simulation`, outside `D:\Python Project\OfficeAutomationSuite-Karina`.
- Dummy Application Root and dummy Data Root were separate per scenario.
- Dummy database was created from scratch with non-production SQLite metadata.
- Dummy recorder profile was non-sensitive JSON.
- Dummy application executables were built from simulation-only source scripts with PyInstaller.
- OAS-K production executable and production database were not used.
- Hashes were captured before and after each scenario.
- Updater ran as current user; no administrator prompt or elevation path was observed.

## 4. Happy Path

Setup:

- Scenario root: `D:\OAS-K_Update_Simulation\Scenarios\HappyPath`
- Application Root before update: dummy `1.0.0`
- Staged Application: dummy `1.0.1` success executable
- Transaction ID: `76809ff9-d90a-471f-a172-d066ad6f2792`

Command:

```powershell
D:\Python Project\OfficeAutomationSuite-Karina\dist\updater\OAS-K-Updater.exe `
  --transaction D:\OAS-K_Update_Simulation\Scenarios\HappyPath\Data\update\transactions\76809ff9-d90a-471f-a172-d066ad6f2792\transaction.json `
  --wait-pid 3112 `
  --shutdown-timeout 15 `
  --health-timeout 10 `
  --log-path D:\OAS-K_Update_Simulation\Scenarios\HappyPath\Data\update\logs\update_76809ff9-d90a-471f-a172-d066ad6f2792.log
```

Observed:

- Start: `2026-07-30T12:42:55`
- Finish: `2026-07-30T12:42:59`
- Old dummy PID: `3112`
- New dummy PID: `26048`
- Exit code: `0`
- Final transaction status: `SUCCESS`

Status timeline:

```text
STAGED -> APPLY_REQUESTED -> WAITING_FOR_SHUTDOWN
-> BACKING_UP_APPLICATION -> APPLYING -> APPLICATION_REPLACED
-> STARTING_NEW_APPLICATION -> HEALTHCHECK_PENDING -> SUCCESS
```

Validation:

- Active Application Root version after update: `1.0.1`
- `new_application_marker.txt`: present
- `old_application_marker.txt`: absent from active Application Root
- Rollback backup exists and contains `version.txt = 1.0.0`
- Rollback backup contains old dummy executable and old marker
- Health-check marker exists
- Health-check transaction ID matches
- Health-check application version: `1.0.1`
- Dummy database SHA-256 before/after: unchanged
- Dummy recorder profile SHA-256 before/after: unchanged
- Updater log sensitive token scan: clean
- Repository status before/after scenario: unchanged

Database:

```text
D:\OAS-K_Update_Simulation\Scenarios\HappyPath\Data\database\OAS-K.db
SHA-256 before/after:
5078ee5d38f35839e9fc19eb0b8b0d1d7c251aba06c143f45f078a0a8da82d43
```

Recorder profile:

```text
D:\OAS-K_Update_Simulation\Scenarios\HappyPath\Data\recorder_profiles\hris\test_profile.json
SHA-256 before/after:
c52e41222aea4f31dbcebe36e355d7d1bd7861374ccf53892c27d276bb3b746e
```

Result: PASS

## 5. Rollback Path

Failure method: new dummy `1.0.1` executable launched and exited without writing a health-check marker. Updater detected health-check timeout and rolled back.

Setup:

- Scenario root: `D:\OAS-K_Update_Simulation\Scenarios\RollbackPath`
- Application Root before update: dummy `1.0.0`
- Staged Application: dummy `1.0.1` crashing executable
- Transaction ID: `c2c76f36-6dd9-4a3f-ae85-8d0941730eb0`

Command:

```powershell
D:\Python Project\OfficeAutomationSuite-Karina\dist\updater\OAS-K-Updater.exe `
  --transaction D:\OAS-K_Update_Simulation\Scenarios\RollbackPath\Data\update\transactions\c2c76f36-6dd9-4a3f-ae85-8d0941730eb0\transaction.json `
  --wait-pid 24828 `
  --shutdown-timeout 15 `
  --health-timeout 5 `
  --log-path D:\OAS-K_Update_Simulation\Scenarios\RollbackPath\Data\update\logs\update_c2c76f36-6dd9-4a3f-ae85-8d0941730eb0.log
```

Observed:

- Start: `2026-07-30T12:43:00`
- Finish: `2026-07-30T12:43:10`
- Old dummy PID: `24828`
- Failed new dummy PID: `11544`
- Exit code: `16`
- Final transaction status: `ROLLED_BACK`
- Last error: `Health check failed or timed out.`

Status timeline:

```text
STAGED -> APPLY_REQUESTED -> WAITING_FOR_SHUTDOWN
-> BACKING_UP_APPLICATION -> APPLYING -> APPLICATION_REPLACED
-> STARTING_NEW_APPLICATION -> HEALTHCHECK_PENDING
-> ROLLBACK_REQUESTED -> ROLLBACK_IN_PROGRESS -> ROLLED_BACK
```

Validation:

- Active Application Root restored version: `1.0.0`
- `old_application_marker.txt`: present
- Old dummy executable present
- `post_rollback_marker.txt`: present
- Failed application diagnostics folder exists
- Failed application is not active
- Rollback backup remains available
- Dummy database SHA-256 before/after: unchanged
- Dummy recorder profile SHA-256 before/after: unchanged
- Data Root stayed in place
- Updater log sensitive token scan: clean
- Repository status before/after scenario: unchanged

Database:

```text
D:\OAS-K_Update_Simulation\Scenarios\RollbackPath\Data\database\OAS-K.db
SHA-256 before/after:
5078ee5d38f35839e9fc19eb0b8b0d1d7c251aba06c143f45f078a0a8da82d43
```

Recorder profile:

```text
D:\OAS-K_Update_Simulation\Scenarios\RollbackPath\Data\recorder_profiles\hris\test_profile.json
SHA-256 before/after:
c52e41222aea4f31dbcebe36e355d7d1bd7861374ccf53892c27d276bb3b746e
```

Result: PASS

## 6. Interrupted Transaction Recovery

Tested: yes

Setup:

- Scenario root: `D:\OAS-K_Update_Simulation\Scenarios\InterruptedRecovery`
- Transaction ID: `70488fab-c2a1-4017-808d-6b5f378927f2`
- Simulated non-terminal status: `APPLICATION_REPLACED`

Result:

- Non-terminal transaction detected: yes
- Recommendation: `Restore Previous Application`
- Data Root remained available
- No file deletion was performed

Result: PASS

## 7. Logs and Artifacts

Happy path:

```text
D:\OAS-K_Update_Simulation\Reports\happy_path_report.json
D:\OAS-K_Update_Simulation\Reports\happy_path_report.txt
D:\OAS-K_Update_Simulation\Scenarios\HappyPath\Data\update\transactions\76809ff9-d90a-471f-a172-d066ad6f2792\transaction.json
D:\OAS-K_Update_Simulation\Scenarios\HappyPath\Data\update\transactions\76809ff9-d90a-471f-a172-d066ad6f2792\healthcheck_success.json
D:\OAS-K_Update_Simulation\Scenarios\HappyPath\Data\update\logs\update_76809ff9-d90a-471f-a172-d066ad6f2792.log
D:\OAS-K_Update_Simulation\Scenarios\HappyPath\Data\update\rollback\76809ff9-d90a-471f-a172-d066ad6f2792
```

Rollback path:

```text
D:\OAS-K_Update_Simulation\Reports\rollback_path_report.json
D:\OAS-K_Update_Simulation\Reports\rollback_path_report.txt
D:\OAS-K_Update_Simulation\Scenarios\RollbackPath\Data\update\transactions\c2c76f36-6dd9-4a3f-ae85-8d0941730eb0\transaction.json
D:\OAS-K_Update_Simulation\Scenarios\RollbackPath\Data\update\logs\update_c2c76f36-6dd9-4a3f-ae85-8d0941730eb0.log
D:\OAS-K_Update_Simulation\Scenarios\RollbackPath\Data\update\rollback\c2c76f36-6dd9-4a3f-ae85-8d0941730eb0
D:\OAS-K_Update_Simulation\Scenarios\RollbackPath\Data\update\failed\c2c76f36-6dd9-4a3f-ae85-8d0941730eb0\application
```

Interrupted recovery:

```text
D:\OAS-K_Update_Simulation\Reports\interrupted_recovery_report.json
```

## 8. Regression Test

Commands:

```powershell
git status --short
git diff --check
py -m pytest tests\update -v
py -m pytest
```

Results:

```text
tests\update -v: 43 passed, 1 warning in 6.97s
full regression: 700 passed, 1 skipped, 1 warning in 200.41s
```

Warning:

```text
tests/update/test_update_package.py::test_duplicate_path_rejected
UserWarning: Duplicate name: 'application/OAS-K.exe'
```

This warning is intentional for the duplicate-path rejection test.

`git diff --check` result: clean, with only Windows LF-to-CRLF warnings.

## 9. Risks and Limitations

- SmartScreen and publisher signing are not handled.
- Update remains application-only.
- Database migration is not enabled.
- Application Root must be writable by the current user.
- Simulation used dummy executables, not the real OAS-K EXE.
- Not tested on an office computer.
- Not tested under antivirus interference.
- Not tested against a real copied OAS-K application sandbox yet.
- Power-loss recovery detector was tested at service level only; full manual restore UX still needs sandbox validation.

## 10. Final Decision

`READY_FOR_REAL_APPLICATION_SANDBOX_TEST`

Do not use `READY_FOR_OFFICE_DEPLOYMENT` yet.

## 11. Recommended Next Step

1. Commit/push Sprint 2 after review.
2. Create a real application sandbox using a copy of the OAS-K application folder, not the office installation.
3. Run the same happy-path and rollback-path flow against that sandbox.
4. Only after sandbox success, plan a controlled office pilot.
