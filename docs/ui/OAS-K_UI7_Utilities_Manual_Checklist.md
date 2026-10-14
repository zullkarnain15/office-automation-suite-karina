# OAS-K UI7 Utilities Manual Checklist

Test boundary: source launcher, Fake Registry, isolated temporary Data Root, and fixture/test sources only. No production database or Registry was used.

## Executed acceptance

- [x] `py tools/ui_test/run_unified_ui.py --test-data-root <temporary-path>` launched successfully and remained responsive during the smoke window.
- [x] The test Data Root was not created merely by launching/opening Utilities.
- [x] Fake Registry recorded zero writes/deletes.
- [x] Utilities landing opens with exactly Comparison Result and Attachment Consolidation.
- [x] Landing performs no defaults load, folder scan, engine call, output creation, database creation, or job creation.
- [x] Both workspaces open internally and return to the landing without a `Toplevel`.
- [x] SQLite unavailable is presented without creating a database; Unified UI run resolution is blocked and Settings remains available.
- [x] Comparison shows distinct Attendance/Outlook inputs, calendar-backed period fields, global/manual output, validation, confirmation, run/cancel, log, result, and recovery controls.
- [x] Attachment shows explicit source input, Excel/TXT attachment mode within the consolidation workflow, scan-subfolders, SQLite TXT Max Lines, per-run override, validation, confirmation, run/cancel, log, result, and recovery controls.
- [x] Pre-validation is read-only and does not create output or history.
- [x] Shared TaskRunner keeps widget access on the Tk thread and restores busy/navigation state.
- [x] Existing safe engine fixtures produce the frozen Comparison report and Attachment TXT/report artifacts; cancellation and partial audit artifacts remain covered by engine regression tests.
- [x] Dashboard and History read normalized `UTILITIES` jobs.
- [x] Standalone Merge TXT/Excel, Split TXT, and Cleansing Excel do not appear as active landing features.
- [x] 1000×640/DPI-scaled source-GUI capture was inspected: cards remain readable and the operational workspace uses a scrollable responsive grid. Existing centralized DPI/visual-contract tests pass.

## Commands and evidence

```text
py -m pytest tests/ui/utilities -q
16 passed

py -m pytest tests/ui -q
221 passed

py -m pytest tests/database tests/storage tests/recovery tests/ui -q
459 passed, 1 skipped

py -m pytest -q
595 passed, 1 skipped

py -m pytest tests/test_attachment_consolidation.py tests/test_attendance_reconciliation_engine.py tests/test_attendance_reconciliation_matcher.py tests/test_attendance_reconciliation_normalizer.py tests/test_attendance_reconciliation_readers.py -q
34 passed

py -m ruff check ui tests/ui tools/ui_test
All checks passed!
```

The single skip is the existing optional environment-dependent case; the real Tk shell smoke and UI7 zero-side-effect smoke passed in this environment.
