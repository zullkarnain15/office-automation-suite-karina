# OAS-K UI4 Attendance Manual Checklist

Date: 2026-07-21
Launcher: `py tools/ui_test/run_unified_ui.py --test-data-root <temporary-path>`
Fixture: temporary `.xlsx`, empty fixture `.mdb` files, fake engine, Fake Registry

- [x] Source launcher opens the Unified UI with a test Data Root.
- [x] Opening the UI/Attendance page starts no engine and reads no workbook.
- [x] Opening with an uninitialized test root creates no folder or database.
- [x] Fake Registry receives no UI-time write/delete.
- [x] Attendance remains in the existing window; no module Toplevel opens.
- [x] Configuration Browse selects the fixture workbook.
- [x] Explicit validation uses the legacy reader and creates no output/job.
- [x] HO selects the HO fixture source.
- [x] BRANCH selects the Branch fixture source independently.
- [x] Global period populates fields and makes them read-only.
- [x] Manual period accepts strict `YYYY-MM-DD` overrides.
- [x] Global output populates the field and makes it read-only.
- [x] Manual output Browse selects the isolated output root.
- [x] TXT and Excel report options are present; one output is required.
- [x] Confirmation is observed before every job-history insert.
- [x] Background run keeps the Tk event loop responsive.
- [x] Stage progress and timestamped log events appear incrementally.
- [x] Cancel enters the safe-checkpoint message and ends `CANCELLED`.
- [x] Partial cancel outputs remain and their five file roles are recorded.
- [x] Successful result summary and guarded Open Output/Open Log work.
- [x] Fixture engine failure shows FAILED and is recorded with its summary.
- [x] Navigation is blocked during a run and restored for all terminal outcomes.
- [x] History and Dashboard pages open after Attendance jobs and read them.
- [x] Job lifecycle observed: `COMPLETED`, `CANCELLED`, `FAILED`.
- [x] Database remains schema v1 with exactly 24 tables.
- [x] `attendance.gui.AttendanceGUI` remains importable.
- [x] Outlook Revisi, HRIS, and Utilities are not connected or run.
- [x] No production database, production Registry, EXE, build, or dist is made.

The persistent fixture acceptance is
`tests/ui/attendance/test_attendance_fixture_acceptance.py`. The source launcher
was also started for three seconds using a unique nonexistent temporary root;
the window started and the root/database remained absent after it was closed.
Fixture artifacts existed only below pytest/system temporary directories.

Manual fallback: run the legacy Attendance launcher/GUI with the legacy
configuration workbook and an explicitly chosen manual output location. Unified
UI does not auto-launch, auto-retry, or modify that configuration.
