# OAS-K UI2 Settings Architecture

Status: COMPLETED
Schema: v1 unchanged (24 tables)
Engine integration: None
Legacy launcher/configuration reader: Unchanged

## Settings sections

The UI1 shell now hosts five internal `ttk.Notebook` sections:

1. General
2. Storage & Database
3. Import / Export Configuration
4. Backup & Recovery
5. HRIS Recorder Profiles

Opening Settings constructs widgets only. It does not resolve storage, create a
folder/database, write Registry, import a workbook, or run recovery. Read-only
status and all mutations start from explicit buttons.

## Service injection

`AppContext.app_services` contains one explicit `AppServices` instance. It
provides database, storage, configuration, recovery, recorder-profile, task,
dialog, and filesystem facades. Widgets receive typed UI values and contain no
SQL or Registry calls. Automated tests inject fakes or fake Registry backends.

There is no global connection, global service locator, or engine object.

## Task runner and busy state

`TaskRunner` owns a two-worker `ThreadPoolExecutor`. Workers publish completed
results into a thread-safe queue. A drain scheduled and rescheduled exclusively
by the Tk thread invokes completion callbacks; workers never call `Tk.after`
and never update widgets. Initial progress is also scheduled by the submitting
Tk thread.
Settings disables registered action buttons while work runs. Destructive tasks
block navigation through `can_navigate_away`.

Cancellation is cooperative. Database activation, SQLite backup, relocation,
restore, and reset are marked non-cancellable after submission. Close stops
new submissions and requests cancellation for pending work.

## Confirmation model

Browse never saves. General Settings show an old/new summary before saving.
Initialize asks for operation confirmation and a separate Registry choice.
Relocation explains that source data is retained. Existing export/template/profile
targets require overwrite confirmation. Restore/import require candidate review
and explicit confirmation. Reset requires exact `RESET` plus a second
confirmation.

No automatic import, restore, or reset exists.

## Global and module settings

`DatabaseSettingsService` reads/saves `global_settings` through the DB1
repository, validates paired ordered ISO dates, and records changed keys using
`AuditRepository` with source `Unified UI`. Saving never creates the output
folder.

Module global-usage controls are derived from actual schema columns:

- Attendance, Outlook Revisi, HRIS, and Comparison support output and period.
- Attachment Consolidation supports output only.
- A module singleton that is not configured is displayed unavailable rather
  than being synthesized with incomplete business fields.

## Storage and database

Storage status is read-only and includes resolution, Data Root/database paths,
existence/validity, schema/application versions, Registry status, and standard
folders. Explicit actions wrap DB3 bootstrap/relocation and DB1 validation.
Relocation defaults to database plus recorder profiles, excludes output/logs,
and never deletes the source.

## Configuration import/export

UI2 supports multiple workbook selection, DB2 read-only preview, detailed
changes/issues, explicit global conflict values, high-risk confirmation,
atomic per-module commit, current configuration export, template folder
opening, and template Save Copy As. Preview never writes. The repository
template is never edited.

## Backup and recovery

DB4 workflows exposed manually are Backup Database, Backup Application Data,
Restore from Backup, Import Existing Database, Reset to Default, and Recovery
Status. Application-data backup always includes recorder profiles; logs and
diagnostics are optional and output remains excluded.

Restore/import display candidate validation, keep the source, and show
pre-operation backup/rollback outcomes. Recovery Status only describes manual
choices.

## Recorder profile storage

The section lists JSON filename, relative path, timestamp, and validation
status. Import requires a JSON object and copies only into the active
`recorder_profiles/hris` folder. Duplicate names require confirmation.
Absolute/traversal references are rejected. Remove Reference changes only the
current UI selection and never deletes the file. UI2 does not edit or execute
steps and does not implement a macro recorder.

## Errors and manual fallback

Technical exceptions are logged; dialogs show bounded Indonesian messages, not
tracebacks. Folder opening uses guarded `os.startfile` and shows the path when
unsupported. All DB1–DB4 manual CLIs remain available.

## Technical debt and UI3

UI2 does not yet provide granular progress from long DB operations because the
underlying DB1–DB4 APIs are atomic calls. Import preview multiline detail,
per-module selection polish, recovery backup discovery, retention/ACL policy,
and full accessibility/DPI review remain.

UI3 should activate read-only Dashboard, History, and System Health views using
the same injected facade/task model. Operational engines must remain gated
until their individual page/background/cancellation contracts are approved.

## Final verification (2026-07-21)

- UI2/settings: `82 passed`.
- Storage/database/recovery/UI regression: `321 passed`.
- Entire project: `457 passed`.
- Ruff (`ui tests/ui tools/ui_test`): all checks passed.
- Real Tk smoke opened all five Settings sections using Fake Registry and a
  pytest temporary Data Root. It observed zero action-service calls, zero
  Registry writes/deletes, no Data Root folder, and no database.
- Source-only manual launcher opened a responsive window titled
  `Office Automation Suite – Karina`; no package/build/export was run.
- `REQUIRED_TABLES` remains exactly 24 and all operational engine imports remain
  forbidden from `ui` by automated boundary tests.
