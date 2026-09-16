# OAS-K Sprint UI2 Final Report

Date: 2026-07-21
Status: COMPLETED
Scope stopped at UI2; UI3 has not started.

## Delivered structure

The single-window shell injects one `AppServices` container into Settings. The
container exposes storage, database settings, configuration import/export,
recovery, recorder-profile, task-runner, dialog, and filesystem facades. UI
widgets do not contain SQL, Registry access, or operational-engine imports.

Settings contains exactly these five lazy in-window sections:

1. General
2. Storage & Database
3. Import / Export Configuration
4. Backup & Recovery
5. HRIS Recorder Profiles

All mutations require an explicit user action. Destructive work blocks
navigation, disables registered actions, and always restores busy state after
success or failure. Worker results cross a thread-safe queue and are delivered
by a Tk-thread polling callback; workers do not call Tk or touch widgets.

## Acceptance evidence

| Check | Final result |
|---|---|
| `py -m pytest tests/ui` | 82 passed |
| `py -m pytest tests/storage tests/database tests/recovery tests/ui` | 321 passed |
| `py -m pytest` | 457 passed |
| `py -m ruff check ui tests/ui tools/ui_test` | All checks passed |
| Fake Registry / temporary Data Root Settings smoke | 2 Tk smoke tests passed |
| Manual source launcher | Responsive window opened with expected title |

The Settings smoke used `FakeRegistryBackend` and a pytest temporary path, not
`D:\OAS-K\Data`. Opening Settings produced no database, no directory, no
Registry write/delete, and no calls to initialize/bootstrap, relocate,
configuration preview/commit/export, database backup, application-data backup,
restore, database import, or reset. All five notebook sections were present.

The schema remains v1 with exactly 24 required tables. Attendance, Outlook
Revisi, HRIS, and Utilities engines are not imported or connected by `ui`.
`main.py`, Configuration Reader, legacy workbooks, and the unified template were
not changed during finalization. No production database, production Registry,
EXE, build, or `dist` output was created.

## UI2 source inventory

New UI2 source is organized under:

- `ui/`: shell, context, page registry/navigation, five Settings section
  modules, dialogs, widgets, and injected service facades.
- `tests/ui/`: navigation, boundary, metadata, Settings/service contracts,
  task-threading, busy-state, and real-Tk side-effect smoke coverage.
- `tools/ui_test/run_unified_ui.py`: source-only manual launcher with optional
  Fake Registry and test Data Root.
- `docs/ui/OAS-K_UI2_Settings_Architecture.md`: architecture and verification.
- `docs/ui/OAS-K_UI2_Manual_Test_Checklist.md`: manual acceptance checklist.
- `docs/ui/OAS-K_UI2_Final_Report.md`: this report.

Finalization specifically modified:

- `ui/services/task_runner.py`
- `tests/ui/services/test_task_and_recovery_services.py`
- `tests/ui/settings/test_settings_contracts.py`
- `tests/ui/test_tk_smoke.py`
- `docs/ui/OAS-K_UI2_Settings_Architecture.md`
- `docs/ui/OAS-K_UI2_Final_Report.md`

Existing unrelated and earlier-sprint worktree changes were preserved and not
reset.

## Technical debt

- Long DB1–DB4 operations expose coarse task progress because their APIs are
  atomic.
- Configuration preview needs improved multiline detail and per-module
  selection polish.
- Recovery backup discovery, retention, and ACL policy remain future work.
- A broader keyboard, screen-reader, high-DPI, and localization pass remains.
- Task cancellation is cooperative; non-cancellable destructive phases must
  continue to remain explicitly identified.

## UI3 recommendation

UI3 should add read-only Dashboard, History, and System Health views through the
same injected service and Tk-thread task model. Keep operational engines gated
until each page has approved background-work, cancellation, and recovery
contracts. Do not alter schema v1 merely to activate those read-only views.
