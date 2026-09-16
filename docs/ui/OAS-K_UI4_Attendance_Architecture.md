# OAS-K UI4 Attendance Architecture

Status: COMPLETED
Schema: v1 unchanged (24 tables)
Connected engine: Attendance only

## Boundary and typed contract

The single-window Attendance page calls `AttendanceService`; the service calls
`AttendanceAdapter`; only the adapter imports the frozen
`AttendanceProcessEngine` and legacy `AttendanceConfigurationReader`. Widgets
never import or invoke an engine. `AppServices` injects the service, and
`AttendanceServiceProtocol` allows page tests to replace it with a fake.

Typed requests, resolved requests, validation/source details, progress/log
events, cancellation tokens, output files, defaults, and run results live in
`ui.attendance_models`. A request records the selected workbook, exactly one
workflow (`HO` or `BRANCH`), global/manual choices, period, output root, and TXT
and report flags. A resolved request freezes the actual values for one job.

## Configuration and request resolution

The configuration path is session-only. Page construction and first show do not
read the workbook. Explicit Validate or Run preflight checks `.xlsx`, existence,
strict ISO dates, `start <= end`, at least one output, and an existing writable
ancestor of the output root without creating it. The legacy reader then opens
the workbook read-only and selects only `ho_mdb_list` or `branch_mdb_list`.
Active MDB paths are checked for file existence/readability; no MDB query runs
during preflight and the workbook is never modified.

If an active database exists, defaults come from `global_settings` and the two
Attendance global-use flags. Global selections make the fields read-only.
Manual overrides remain per-job values and never update global/module settings.
Without a database, manual validation remains available but Unified UI Run is
blocked with guidance to initialize Data Location; the legacy GUI/workbook path
remains the fallback.

## Engine call and task lifecycle

After successful preflight and explicit confirmation, the service writes
`PENDING`, then `RUNNING`, and calls:

```text
AttendanceProcessEngine.run(
    configuration=<legacy reader result>,
    output_root=<resolved Path>,
    workflow="HO" | "BRANCH",
    date_from=<datetime>,
    date_to=<datetime>,
    generate_txt=<bool>,
    generate_report=<bool>,
)
```

The engine has no callback or safe interruption hook. The adapter therefore
emits honest stage-based events around configuration loading, engine execution,
and finalization; it does not invent percentages. `TaskRunner.submit_reporting`
places plain progress/log objects on its queue. Only the Tk-thread drain invokes
page callbacks, so workers never touch widgets. The log view is capped at 500
lines and supports Copy and Clear View without deleting `Process.log`.

Cancellation is cooperative. The token is checked before/after configuration
and after the synchronous engine stage. A request during the engine displays
that cancellation waits for the current stage. It records controlled unified
status `PAUSED` with legacy/phase `CANCEL_REQUESTED`, then finishes as
`CANCELLED`. An immediate transaction and terminal-state guard prevent a late
cancel marker from overwriting `COMPLETED`, `FAILED`, or `CANCELLED`. Existing
partial artifacts are retained and recorded.

## Audit and recovery

Terminal unified statuses are `COMPLETED`, `FAILED`, and `CANCELLED`; successful
legacy status is `SUCCESS`. Actual output/period/global flags are written to
`job_history`, together with counts, timestamps, duration, source summary,
process-log/summary paths, and a concise error. Existing artifacts only are
written to `job_files` using `OUTPUT_FOLDER`, `HRIS_TXT`, `EXCEL_REPORT`,
`PROCESS_LOG`, and `SUMMARY_JSON`. Full process logs are not stored in SQLite.

The result area shows status, job/workflow, counts, file count, output, and
error summary. Guarded actions open output/log/configuration folders, prepare a
new job, or return to Settings. There is no auto-retry or configuration rewrite.
The legacy `attendance.gui.AttendanceGUI` remains available for manual fallback.

## Frozen boundaries and debt

No Attendance business rule, pairing/validation logic, TXT/report format,
legacy reader, workbook/template, schema, or old GUI was changed. Outlook
Revisi, HRIS, and Utilities remain unconnected.

The principal debt is coarse progress and delayed cancellation while the legacy
engine is inside its synchronous stage. A future backward-compatible engine
callback/checkpoint could improve granularity, but only with separate engine
regression approval. Job finalization is robust against adapter exceptions;
failures in SQLite itself still depend on the repository/database recovery
layer.
