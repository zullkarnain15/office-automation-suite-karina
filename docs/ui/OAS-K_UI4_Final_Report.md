# OAS-K Sprint UI4 Final Report

Date: 2026-07-21
Status: COMPLETED
Work stopped after UI4.

## Delivered

- Active Attendance page with Configuration, Period, Workflow, Output Options,
  Output Location, Validation Summary, Progress, Process Log, Result Summary,
  and guarded recovery actions.
- Typed page/service/adapter boundary using the actual legacy configuration
  reader and `AttendanceProcessEngine.run` contract.
- HO/BRANCH single-workflow jobs, global/manual period and output resolution,
  pre-validation, explicit confirmation, background execution, coarse progress,
  bounded logs, cooperative cancellation, result/error recovery, and manual
  legacy fallback.
- Job audit lifecycle with controlled schema statuses, actual resolved values,
  status events, result counts, errors, and references for existing output
  folder/TXT/report/process-log/summary files only.
- Queue-backed TaskRunner reporting whose callbacks return on the Tk thread.
- Cancellation race protection so late requests cannot overwrite a terminal job.

## Verification

| Scope | Result |
|---|---|
| `py -m pytest tests/ui/attendance` | 7 passed |
| Relevant Attendance engine regression | 34 passed |
| `py -m pytest tests/ui` | 123 passed |
| `py -m pytest tests/database tests/storage tests/recovery tests/ui` | 361 passed, 1 optional Tk skip |
| `py -m pytest` | 497 passed, 1 optional Tk skip |
| `py -m ruff check ui tests/ui tools/ui_test` | All checks passed |
| Schema | v1, exactly 24 tables |
| Fixture acceptance | PASS: COMPLETED/CANCELLED/FAILED |
| Source launcher | Window started; no test-root/database creation |

The final test rerun is the authority for these counts. The single optional Tk
skip can occur when a test cannot acquire a display; the same Attendance/Tk
scope passed 7/7 in its immediate dedicated rerun, the full UI suite passed
123/123, and the persistent real-Tk fixture acceptance passed.

## Safety and compatibility

Opening Attendance itself performs no workbook read, database creation, folder
creation, Registry write, bootstrap, or engine execution. Validate is read-only
and writes no job. Run is blocked when the audit database is unavailable. The
manual source launcher used Fake Registry plus a unique temporary test root;
the automated acceptance created its schema and outputs only under a pytest
temporary directory. No production database/Registry, EXE, build, or dist was
created.

Attendance pairing, validation, deduplication, TXT formatting/splitting, Excel
report structure, output-folder contract, and reconciliation regressions remain
unchanged. The legacy GUI remains importable. `main.py`, schema v1, Configuration
Reader, legacy workbook, unified template, assets, other engines, and packaging
files were not changed by UI4. Outlook Revisi, HRIS, and Utilities remain
unconnected.

## New files

- `ui/attendance_models.py`
- `ui/adapters/__init__.py`
- `ui/adapters/attendance_adapter.py`
- `ui/services/attendance_service.py`
- `tests/ui/adapters/__init__.py`
- `tests/ui/adapters/test_attendance_adapter.py`
- `tests/ui/attendance/__init__.py`
- `tests/ui/attendance/test_attendance_page.py`
- `tests/ui/attendance/test_attendance_fixture_acceptance.py`
- `tests/ui/services/test_attendance_service.py`
- `docs/ui/OAS-K_UI4_Attendance_Architecture.md`
- `docs/ui/OAS-K_UI4_Attendance_Manual_Checklist.md`
- `docs/ui/OAS-K_UI4_Final_Report.md`

## Updated files

- `ui/pages/attendance_page.py`
- `ui/services/protocols.py`
- `ui/services/service_container.py`
- `ui/services/task_runner.py`
- `shared/database/repositories/job_repository.py`
- `tests/ui/services/test_task_and_recovery_services.py`
- `tests/ui/test_boundaries.py`

## Technical debt and UI5 recommendation

Legacy engine execution remains synchronous, so progress is deliberately coarse
and cancellation waits for the current engine stage. A future callback/token
hook would require a separately approved, backward-compatible engine change and
full output regression. Accessibility, richer source progress, and more detailed
error categories can also improve without changing business logic.

UI5 should connect only the next explicitly approved module through its own
typed adapter/service. Reuse the TaskRunner reporting, confirmation, cancellation
race guard, and job-audit patterns; do not place operational engines in widgets
or AppContext and do not combine modules in one job. UI5 has not been started.
