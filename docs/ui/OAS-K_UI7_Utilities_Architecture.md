# OAS-K UI7 Utilities Architecture

## Scope

UI7 activates one sidebar entry, **Utilities**, with three internal workspaces:

1. **Comparison Result** — Attendance is the main source and Outlook Revisi is the supporting revision source.
2. **Attachment Consolidation** — explicitly scans an Outlook Revisi attachment folder and produces the existing HRIS-compatible TXT/report artifacts.

Legacy standalone Merge TXT, Merge Excel, Split TXT, and Cleansing Excel tools are not exposed as active landing features.

## Boundaries

The dependency flow is:

`UtilitiesPage -> typed service -> typed adapter -> existing Utilities engine`

The page imports only UI models and services. Engine imports are isolated in `ui/adapters`. `AppServices` owns the service instances; no engine is stored directly in `AppContext`.

The landing renders three lightweight summaries only. It does not resolve storage, load SQLite, inspect a folder/file, create output, create a job, or run an engine. Defaults are loaded asynchronously only after a workspace is opened.

## SQLite configuration

`UtilitiesService.load_defaults()` opens the active database read-only and reads only existing schema-v1 fields:

- `global_settings.output_root`, `period_start`, `period_end`;
- `comparison_settings.use_global_output`, `use_global_period`, `updated_at`;
- `attachment_consolidation_settings.use_global_output`, `txt_max_lines`, `updated_at`.

Global values are copied into a resolved per-job request. Manual source, period, output, and advanced TXT-line overrides are session-only and are never written back to SQLite. Output parents are checked without creating the requested output folder. Attachment source equal to output is blocked.

## Comparison Result

`ComparisonResultAdapter` constructs the existing `ReconciliationRequest` and uses:

- `ReconciliationEngine.scan(..., read_only=True)` for explicit pre-validation;
- `ReconciliationEngine.run(request, scan, cancel_event)` after confirmation and audit-job creation.

The read-only engine hook is optional and backward-compatible; default engine callers retain the previous validation behavior. Status codes come directly from `ALL_COMPARISON_STATUSES`; no classification or correction logic is copied into UI code. Existing writer behavior preserves `Guide_Status` as the first sheet, report identity, formatting, and output naming.

## Attachment Consolidation

`AttachmentConsolidationAdapter` uses:

- `AttachmentConsolidationEngine.scan(request, cancel_event)` for explicit, non-destructive inspection;
- `AttachmentConsolidationEngine.run(..., txt_max_lines=<SQLite/per-run value>)` for execution.

The optional `txt_max_lines` hook bypasses the legacy Outlook configuration reader only when a typed value is supplied. Existing callers that omit it retain their previous behavior. Source files are read only; the engine creates a separate job folder and retains invalid/partial results in its report, summary, and process log.

## Background work, progress, and cancellation

Preflight and execution run through the shared `TaskRunner`. Workers publish typed plain-data progress/log events to its queue; Tk callbacks run only in the queue drain scheduled by `root.after`. Page callbacks ignore results after disposal. Busy state is cleared on success and failure. A running job blocks page navigation and close.

Cancellation uses `threading.Event` through typed tokens. Engines observe cooperative checkpoints. Cancellation never terminates a thread. The audit writer uses a transaction and checks terminal status so a late cancel cannot overwrite a completed, failed, or cancelled job.

## Audit and file references

Jobs use `module_code=UTILITIES`. Because schema v1 constrains `job_history.workflow` to `HO` or `BRANCH`, the subfeature is stored in `feature_code` as `COMPARISON_RESULT` or `ATTACHMENT_CONSOLIDATION`; the workflow column remains schema-valid.

Centralized phase constants record creation, carried-forward validation/inspection, engine/write stages, output creation, cancellation request, and terminal completion/failure/cancellation. Only paths that exist are inserted into `job_files`. Controlled roles cover output folders, comparison/consolidation reports, consolidated TXT files, process logs, summaries, and source references. A rejected-files reference is recorded only if an engine actually produces such a separate artifact.

Dashboard already aggregates `UTILITIES`; History reads the same normalized job, event, and file-reference records.

## Recovery and safety

The workspace provides source/output browsing, explicit inspect/validate, confirmation before job creation, process log, result detail, open-output/report/log actions, retry-as-new-job, Settings routing, and an Advanced per-run TXT limit. There is no auto-retry and no automatic source correction or deletion.

No schema, `main.py`, legacy workbook, configuration template, Attendance/Outlook/HRIS business engine, build, dist, or EXE path is part of UI7.

## Sprint 7 Att Data Repair Addendum

The third Utilities workspace is **Att Data Repair**. It reads Attachment
Consolidation `.xlsx` Excel reports, repairs attendance records, and produces
HRIS TXT plus an Excel audit report.

`UtilitiesService.load_defaults()` now also reads `att_data_repair_settings`
read-only: `enabled`, `use_global_output`, `use_global_period`, `generate_txt`,
`generate_excel_report`, `txt_max_rows`, and `updated_at`.

`AttDataRepairService` resolves active SQLite settings through
`AttDataRepairConfigurationService`, applies per-job UI overrides for
`Generate TXT` and `Generate Excel Report`, and builds the existing
`AttDataRepairJobRequest`.

`AttDataRepairAdapter` uses `AttDataRepairReportReader.read()` for
non-destructive workbook preflight and `AttDataRepairEngine.run_job()` for
execution. `AttDataRepairJobAudit.safe_record()` is called from the service
layer after the engine returns.

The UI never reads the source workbook directly, never applies repair rules,
and never writes Att Data Repair settings. Source Report uses a file picker
filtered to `*.xlsx`; folder input, `.xls`, and `.xlsm` are rejected by service
validation. Global/local period and global/local output are resolved before the
engine request is created. The UI passes only an output root; the engine creates
`Utilities\Att_Data_Repair\YYYY-MM\YYYY-MM-DD_XX`.

Status mapping:

| Core status | UI status | History unified status |
| --- | --- | --- |
| SUCCESS | Berhasil | COMPLETED |
| PARTIAL_SUCCESS | Berhasil dengan peringatan | COMPLETED_WITH_WARNING |
| NO_VALID_RECORDS | Tidak ada data valid | COMPLETED_WITH_WARNING |
| FAILED | Gagal | FAILED |
| CANCELLED | Dibatalkan before engine start | Not a core engine status |

Cancellation uses `threading.Event` through typed tokens. Att Data Repair
supports safe pre-engine cancellation checkpoints in the service/adapter; once
`run_job()` starts, cancellation waits until the engine reaches the next safe
service boundary. Cancellation never terminates a thread.

Att Data Repair records feature code `Att Data Repair` and leaves workflow
unset because source records may contain both HO and Branch output in one run.
Controlled file roles include `HRIS_TXT`, `EXCEL_REPORT`, `PROCESS_LOG`, and
`SUMMARY_JSON`.
