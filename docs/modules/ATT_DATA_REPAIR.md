# Att Data Repair

## Purpose

Att Data Repair repairs attendance rows from an Attachment Consolidation Excel
report and produces HRIS-ready TXT output plus an Excel audit report.

## Business Problem

Attachment Consolidation can collect attendance revision rows from Outlook
attachments, but the collected rows may contain spreadsheet errors, inconsistent
date/time formats, missing time values, or records that should be excluded from
HRIS TXT output. Att Data Repair applies deterministic repair rules and records
all changes for audit review.

## Position in Utilities

The Unified UI Utilities landing contains Comparison Result, Attachment
Consolidation, and Att Data Repair. Att Data Repair is launched from the third
card and runs through the shared TaskRunner.

## Input Source

Input is an `.xlsx` Excel report produced by Attachment Consolidation. The UI
uses a file picker filtered to `*.xlsx`.

## Required Sheets

- `Valid_Records`
- `Invalid_Records`

## Required Columns

`Valid_Records` requires `No`, `Source_File`, `Relative_Path`, `Source_Row`,
`Workflow`, `NIK`, `Date_In`, `Time_In`, `Date_Out`, `Time_Out`, `Output_TXT`,
and `Status`.

`Invalid_Records` requires `No`, `Source_File`, `Relative_Path`, `Source_Row`,
`Workflow`, `NIK`, `Date_In`, `Time_In`, `Date_Out`, `Time_Out`, `Status_Code`,
`Reason`, and `Raw_Value`.

## Period Handling

The run uses resolved period start and period end. If `Use_Global_Period` is
enabled, values come from General Settings. If disabled, the UI supplies local
per-job dates. The source workbook is never used as a period fallback.

## NIK Rules

NIK values are normalized as ASCII digit text to preserve leading zeroes. The
repair is deterministic and does not require a master employee lookup.

- Exact 9-digit NIK values are preserved.
- Exact 10-digit official NIK values are preserved unless they match one of the
  agreed mistype signatures.
- A 10-digit value with 5-8 leading zeroes receives a leading `2`.
- A 10-digit value beginning with `2` plus 4-7 zeroes receives one additional
  zero after `2`.
- A 10-digit value beginning with `2` plus exactly 3 zeroes has the extra
  leading `2` removed, restoring the 9-digit NIK.
- An 11-digit value beginning with `2` plus 5-8 zeroes is preserved.
- An 11-digit value with 6-9 leading zeroes has its first zero replaced by `2`
  when the result matches the valid long-NIK pattern.
- Other lengths, non-digit values, spreadsheet errors, and uncertain 11-digit
  patterns are rejected as `INVALID_NIK` anomalies.

NIK changes are recorded with original value, final value, and a dedicated
change code. Duplicate detection uses the repaired final NIK.

## Date Rules

Date values are parsed from workbook values and must be inside the resolved
report period. `Date_Out` is aligned to `Date_In` when repair rules allow it.
Night shift is not supported.

## Time Rules

Supported user data time formats include values such as `7;20` and `7.20`.
Configuration time values are stricter and use `HH:MM`.

## Default Times

Default times come from active SQLite settings. The additional repair keys are
`saturday_missing_out_default` (11:00) and `midnight_time_out_default` (23:59).
The existing weekday defaults are unchanged.

## Duration Minimum

`Minimum_Duration_Minutes` defaults to 61 and is configurable through
`att_data_repair_settings`.

## Duplicate Handling

Duplicate matching requires complete and valid original NIK, Date_In, Time_In,
Date_Out, and Time_Out values. The first exact normalized match is retained and
later matches become `DUPLICATE_RECORD` anomalies. A row with an originally
blank date or time is never a duplicate candidate, even after repair defaults
populate its final values.

## Workflow Handling

Valid workflows are HO and Branch. A single run may produce both HO and Branch
TXT files based on source rows.

## Output Folder

The UI supplies only the output root. The engine creates
`Utilities\Att_Data_Repair\YYYY-MM\YYYY-MM-DD_XX`.

## TXT Naming

TXT output uses `Att_Data_Repair_[Workflow]-[NNN]_[RRRR].txt`. `RRRR` is one
random 4-digit code reused by TXT files in the same job.

## Excel Report Sheets

The audit report contains `Guide_Status`, `Process_Summary`,
`Summary_Per_Karyawan`, `Final_Records`, `Changed_Records`, `Anomaly`,
`Change_Log`, and `Source_Inventory`.

## summary.json

`summary.json` stores schema version, module, engine version, job id, status,
period, source workbook, output paths, counts, TXT metadata, report metadata,
and error information.

## Process.log

`Process.log` records job start, source, period, reader completion, analysis
counts, TXT/report generation or skip, final status, and failures.

## Configuration Sheet

Unified Configuration includes optional sheet `Att_Data_Repair`. Older
workbooks without this sheet remain importable and receive Blueprint defaults.

## SQLite Settings

Active settings live in singleton table `att_data_repair_settings` at schema
v3. Columns include enabled, duration, default times, TXT max rows, generate
flags, global period/output flags, updated timestamp, and updated_by.

## Global/Local Period

Global period uses General Settings. Local period is per-job UI state and is
not persisted to SQLite.

## Global/Local Output

Global output uses General Settings output root. Local output is per-job UI
state and is not persisted to SQLite.

## Generate Flags

`Generate_TXT` and `Generate_Excel_Report` can be overridden for a single UI
job. At least one output must be enabled. Per-job overrides do not write
SQLite.

## UI Flow

Open Utilities, open Att Data Repair, select Source Report, resolve
period/output, choose output options, preflight, confirm, run, review result
summary, and use output/report/log recovery buttons or History.

## Status Mapping

| Core status | UI | History |
| --- | --- | --- |
| SUCCESS | Berhasil | COMPLETED |
| PARTIAL_SUCCESS | Berhasil dengan peringatan | COMPLETED_WITH_WARNING |
| NO_VALID_RECORDS | Tidak ada data valid | COMPLETED_WITH_WARNING |
| FAILED | Gagal | FAILED |

Pre-engine cancellation is represented by the UI as cancelled. The core engine
does not currently expose a persisted mid-run CANCELLED status.

## History Integration

`AttDataRepairJobAudit.safe_record` writes job_history, job_files, and
job_status_events after engine completion. History failure is logged without
deleting generated output.

## Cancellation Limitation

Cancellation is cooperative before the engine starts. Once `run_job()` begins,
the UI waits for the next safe service boundary. No thread is killed forcibly.

## Error Handling

The UI/service layer maps missing source, wrong extension, missing sheets,
missing headers, invalid period, missing global settings, disabled feature, and
both output flags disabled to user-facing Indonesian messages.

## Testing

Coverage includes core analysis, output, report, configuration, migration,
import/export roundtrip, UI service, UI page contract, history, source
immutability, and status parity.

## Known Limitations

- No night shift support.
- Mid-run cancellation is not granular inside `run_job()`.
- Manual visual QA must still be performed on Windows before release.

## Manual Fallback

Advanced users can import/export configuration through the Unified
Configuration workbook and inspect generated Process.log, summary.json, TXT,
and Excel report artifacts directly.

## Future Enhancement

- Granular cancellation checkpoints inside the core engine.
- Dedicated Att Data Repair icon.
- More detailed operator-facing validation copy after manual QA feedback.
