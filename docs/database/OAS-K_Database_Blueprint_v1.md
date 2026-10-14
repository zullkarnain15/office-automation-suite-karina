# OAS-K Database Blueprint v1

Status: Sprint DB0 design proposal
Database file created: No
Target implementation sprint: DB1

## 1. Scope and evidence

This blueprint is based on the current source code, configuration readers,
workbooks, and job artifacts in the OAS-K project. It does not change an
engine, GUI, output format, configuration workbook, or business rule.

Evidence audited:

- `shared.config_manager.AttendanceConfigurationReader`
- `shared.config_manager.OutlookRevisiConfigurationReader`
- `shared.config_manager.HRISConfigurationReader`
- Attendance GUI's direct date read from `General!B8:B9`
- Attachment Consolidation's Outlook configuration resolver
- Comparison Result and Attachment Consolidation request models
- Attendance, Outlook Revisi, HRIS, Comparison Result, and Attachment
  Consolidation result metadata, `Process.log`, and `summary.json` writers
- All sheets and non-empty cells in the three active configuration workbooks
- The HRIS pre-assisted backup and duplicate Outlook workbook as migration
  evidence, not as independent active configuration

No workbook contains formulas, defined names, or external links. The current
files are configuration/master-data workbooks, not calculation workbooks.

## 2. Database role

SQLite is the authoritative store for:

- active configuration after controlled migration;
- global output and period settings;
- job history and normalized job status;
- references to external artifacts;
- configuration change audit;
- configuration import batches;
- backup history;
- System Health snapshots.

SQLite does not replace or embed:

- Attendance raw MDB data;
- HRIS TXT;
- generated Excel reports;
- `Process.log`;
- `summary.json`;
- Outlook attachments;
- Comparison Result workbooks;
- Attachment Consolidation output.

Those files remain operational evidence. SQLite stores their paths, roles,
sizes, optional hashes, and availability state.

Dashboard summaries should be queries or views over `job_history`,
`job_status_events`, and `system_health_history`; a separate persisted
dashboard table is not justified in schema v1.

## 3. Data-root design

Preferred local layout:

```text
D:\OAS-K\Data
├── database
│   └── OAS-K.db
├── backup
├── output
├── logs
└── diagnostics
```

Rules:

1. DB1 should probe whether `D:\OAS-K\Data` is available and writable.
2. If unavailable, the operator selects another local writable folder.
3. The active location will later be referenced from
   `HKEY_CURRENT_USER\Software\OTO Finance\OAS-K`.
4. Registry work is deferred; DB0 and DB1 must not invent a JSON pointer beside
   the EXE.
5. The active database should not be placed on a network share. A network path
   may be accepted only for backup copies after explicit validation.
6. The application must never require administrator rights to write inside
   Program Files or beside the EXE.

## 4. Global output and period

`global_settings` is a singleton row:

| Column | Type | Null | Rule |
|---|---|---:|---|
| `global_settings_id` | INTEGER | No | Primary key; fixed value `1` |
| `output_root` | TEXT | No | Absolute, local, writable directory |
| `period_start` | TEXT | Yes | ISO date `YYYY-MM-DD` |
| `period_end` | TEXT | Yes | ISO date `YYYY-MM-DD` |
| `updated_at` | TEXT | No | ISO timestamp |
| `updated_by` | TEXT | Yes | Operator identity when available |

Constraints:

```sql
CHECK (global_settings_id = 1)
CHECK (
    (period_start IS NULL AND period_end IS NULL)
    OR
    (
        period_start IS NOT NULL
        AND period_end IS NOT NULL
        AND period_start <= period_end
    )
)
```

Output and period selection are independent. Each relevant module settings row
contains separate `use_global_output` and `use_global_period` flags.

Resolution at run time:

```text
output_path_used =
    global.output_root             when use_global_output = 1
    run_request.output_override    when use_global_output = 0

period_start_used / period_end_used =
    global period                  when use_global_period = 1
    run-request override           when use_global_period = 0
```

An override is transient and must not update `global_settings`. Every job
records the resolved values and flags in `job_history`.

Applicability:

| Module/feature | Global output | Global period | Notes |
|---|---:|---:|---|
| Attendance | Yes | Yes | Existing GUI already separates its two source toggles |
| Outlook Revisi | Yes | Yes | Legacy `Payroll_Period` is a month label derived from the resolved period |
| HRIS | Yes | Yes | TXT source remains a run input |
| Comparison Result | Yes | Yes | Both are explicit fields in `ReconciliationRequest` |
| Attachment Consolidation | Yes | No | No period exists in its current request model |
| Merge TXT / Merge Excel | Future | No evidence | No active implementation/configuration exists |

For Outlook migration, `MM-YYYY` can only be converted safely when the operator
confirms that the intended period is the entire month. DB1 must preview the
derived first/last dates; it must not silently guess a custom payroll range.

## 5. Data conventions

- Dates: `YYYY-MM-DD`.
- Timestamps: ISO 8601 with seconds; include offset when known.
- Boolean: INTEGER constrained to `0` or `1`.
- Path: TEXT. Store normalized absolute paths for active locations and preserve
  legacy text in import diagnostics.
- Workflow: TEXT constrained to `HO` or `BRANCH`.
- Reader/writer adapters translate legacy `Branch` to `BRANCH` and back.
- Run Control ID: TEXT, never numeric. Values such as `001` and `02` must remain
  exact.
- Email addresses: TEXT; normalization for matching is case-insensitive, while
  the original casing may be retained for display.
- No password, access token, session cookie, or credential is stored in any
  settings or audit table.

## 6. Schema versioning and connection policy

`database_metadata` is a singleton:

| Column | Type | Rule |
|---|---|---|
| `metadata_id` | INTEGER | PK, fixed `1` |
| `database_uuid` | TEXT | Unique immutable UUID |
| `schema_version` | INTEGER | Positive integer |
| `application_version` | TEXT | OAS-K version that last wrote metadata |
| `created_at` | TEXT | ISO timestamp |
| `updated_at` | TEXT | ISO timestamp |
| `last_migrated_at` | TEXT | Nullable ISO timestamp |

`PRAGMA user_version` and `database_metadata.schema_version` must agree.
Migrations are sequential and never depend on deleting the database.

Initial connection policy:

```sql
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;
```

`DELETE` journal mode is preferred for v1 because OAS-K is a single-user
desktop application and backup/restore should not have to coordinate `-wal`
and `-shm` sidecars. WAL may be reconsidered only after local-path enforcement,
concurrency measurements, shutdown tests, and backup tests. WAL must not be
used to justify an active database on a network share.

Every connection uses context-managed transactions and deterministic close.
Validation uses `PRAGMA quick_check` routinely and `PRAGMA integrity_check`
before activation, restore, import, and backup acceptance.

## 7. Schema v1 table inventory

### 7.1 Core

#### `database_metadata`

- Purpose: schema/application identity and migration state.
- PK: `metadata_id`.
- Unique: `database_uuid`.
- Retention: lifetime of database.
- Required in v1: Yes.

#### `global_settings`

- Purpose: one output root and one optional global period.
- PK: `global_settings_id`.
- Timestamps: `updated_at`.
- Retention: current state; changes copied to `configuration_audit`.
- Required in v1: Yes.

#### `application_preferences`

Columns: `preference_key TEXT PRIMARY KEY`, `preference_value TEXT`,
`value_type TEXT`, `updated_at TEXT`.

- Purpose: small dynamic UI preferences that are not business rules.
- Constraint: `value_type IN ('TEXT','INTEGER','REAL','BOOLEAN')`.
- Do not store module business settings here.
- Required in v1: Yes, but keys must be allow-listed by application code.

### 7.2 Attendance

#### `attendance_settings`

Key columns:

- `attendance_settings_id INTEGER PRIMARY KEY CHECK (... = 1)`
- `use_global_output INTEGER NOT NULL DEFAULT 1`
- `use_global_period INTEGER NOT NULL DEFAULT 1`
- `split_txt_rows INTEGER NOT NULL DEFAULT 10000 CHECK (split_txt_rows > 0)`
- `generate_report_default INTEGER NOT NULL DEFAULT 1`
- `default_workflow TEXT NOT NULL DEFAULT 'HO'`
- `updated_at TEXT NOT NULL`

Unique/singleton: fixed PK `1`.
Required in v1: Yes.
Note: fixed date/time output formats remain business constants until an engine
change is separately approved.

#### `attendance_sources`

Columns:

- `attendance_source_id INTEGER PRIMARY KEY`
- `workflow TEXT NOT NULL`
- `source_code TEXT NOT NULL`
- `source_name TEXT NOT NULL`
- `mdb_path TEXT`
- `is_active INTEGER NOT NULL DEFAULT 1`
- `sort_order INTEGER NOT NULL DEFAULT 0`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Constraints:

- `workflow IN ('HO','BRANCH')`
- boolean check on `is_active`
- `UNIQUE(workflow, source_code)`

Indexes: `(workflow, is_active, sort_order)`.
Retention: retain inactive master rows; do not hard-delete on routine import.
Required in v1: Yes.

No `attendance_reference` table is proposed. The Reference sheet contains
documentation/business-rule prose, not runtime configuration.

### 7.3 Outlook Revisi

#### `outlook_settings`

Singleton columns:

- global flags: `use_global_output`, `use_global_period`
- transport: `integration_method`, `mailbox_smtp`, `source_folder`,
  `reply_from_smtp`, `send_transport`, `smtp_server`, `smtp_port`,
  `smtp_timeout_seconds`, `save_smtp_copy_to_sent`
- workflow behavior: `processed_folder`, `auto_reply_enabled`, `send_mode`,
  `resubmit_deadline`, `txt_max_lines`
- display: `module_display_name`
- timestamps: `updated_at`

Constraints include:

- `send_transport IN ('OUTLOOK','SMTP')`
- `send_mode IN ('SEND','DRAFT')`
- `smtp_port BETWEEN 1 AND 65535`
- `smtp_timeout_seconds > 0`
- `txt_max_lines > 0`
- boolean checks

`mailbox_smtp`, `reply_from_smtp`, and SMTP server values are not credentials.
No password columns are permitted.

#### `outlook_sender_master`

Columns include `sender_id`, `workflow`, `company_code`, `branch_code`,
`sender_nik`, `sender_name`, `sender_email`, `supervisor_nik`,
`supervisor_name`, `required_cc_email`, `is_active`, and timestamps.

PK: `sender_id`.
Defaults: company/branch codes are empty strings for HO.
Unique: `(workflow, company_code, branch_code, sender_email)`.
Indexes: active sender email; `(workflow, company_code, branch_code)`.
Required in v1: Yes. NIK/supervisor fields are retained for lossless
round-trip even though the current reader does not expose them to the engine.

#### `outlook_subject_rules`

Columns: `subject_rule_id`, `workflow`, `subject_pattern`, `is_active`,
timestamps.
Unique: one active logical rule per workflow; enforce
`UNIQUE(workflow, subject_pattern)`.
Required in v1: Yes.

#### `outlook_attachment_rules`

Store one extension per row:
`attachment_rule_id`, `workflow`, `extension`, `is_active`, timestamps.

Unique: `(workflow, extension)`.
Validation: lowercase extension beginning with `.`.
Required in v1: Yes. The importer splits the legacy semicolon list.

#### `outlook_validation_rules`

Columns: `validation_rule_id`, `rule_code`, `workflow`, `rule_value`,
`is_active`, timestamps.

Unique: `(rule_code, workflow)`.
Workflow allows `HO`, `BRANCH`, or `ALL`.
Required in v1: Yes.

#### `outlook_reply_templates`

Columns: `reply_template_id`, `reply_code`, `recipient_type`, `trigger_code`,
`subject_template`, `body_template`, `is_active`, timestamps.

Unique: `reply_code`.
Validation: all `{PLACEHOLDER}` values must belong to the supported placeholder
set for that trigger. Newlines remain TEXT, unchanged.
Required in v1: Yes.

#### `outlook_summary_recipients`

Columns: `recipient_id`, `recipient_type`, `email_address`, `is_active`,
`sort_order`, timestamps.

Unique: `(recipient_type, email_address)`.
Constraint: `recipient_type IN ('TO','CC')`.
Purpose: normalize legacy semicolon-separated PIC/SPV recipient values.
Required in v1: Yes.

### 7.4 HRIS

#### `hris_settings`

Singleton settings include:

- `use_global_output`, `use_global_period`
- `hris_url`
- `browser_channel`, `browser_headless`
- `stop_on_first_failure`
- `click_profile_path`, `manual_recovery_enabled`,
  `require_profile_match`
- `browser_x`, `browser_y`, `browser_width`, `browser_height`,
  `browser_zoom`
- verification enable/timeout/poll/wait flags and phrase lists
- manual verification flags
- `updated_at`

Constraints:

- `hris_url` is required and must not contain embedded credentials.
- browser dimensions have safe minimums.
- zoom is a positive supported percentage.
- wait/poll/timeout values are non-negative and timeout is not less than wait.
- booleans are `0/1`.

Required in v1: Yes.

The currently unused General/Browser/Upload parameters are not promoted to
active columns merely because they exist in Excel. They remain available in
legacy-compatible export until an approved consumer exists.

#### `hris_run_controls`

Columns: `run_control_pk`, `workflow`, `sequence`, `run_control_id TEXT`,
`description`, `is_active`, timestamps.

Unique:

- `(workflow, sequence)`
- `(workflow, run_control_id)`

Indexes: `(workflow, is_active, sequence)`.
Required in v1: Yes.

#### `hris_assisted_steps`

Columns: `assisted_step_id`, `sequence`, `step_name`, `action`,
`input_source`, `method`, `is_required`, `wait_after_seconds`,
`description`, `is_active`, timestamps.

Unique: `sequence`, `step_name`.
Controlled sets match current reader constants for action, input source, and
method.
Required in v1: Yes.

No `hris_reference` table is proposed. The Reference sheet is mandatory to the
legacy reader but its rows are not read or consumed.

### 7.5 Utilities

#### `comparison_settings`

Singleton columns: `use_global_output`, `use_global_period`, `updated_at`.

Purpose: persist only the two requested global-selection defaults. Source mode,
workflow, and input roots remain per-run inputs.
Required in v1: Yes for Unified UI integration; no legacy Excel source exists.

#### `attachment_consolidation_settings`

Singleton columns: `use_global_output`, `txt_max_lines`, `updated_at`.

Purpose: remove the current hidden dependency on Outlook's `TXT_Max_Lines`
without inventing unrelated utility configuration. At initial migration the
value is copied from Outlook, shown in preview, and becomes independent after
commit.
No period column is present.
Required in v1: Yes.

No `utilities_settings`, Merge TXT settings, or Merge Excel settings table is
proposed. Current Merge modules are empty and provide no contract to migrate.

### 7.6 Operational history

#### `job_history`

Key columns:

- `job_pk INTEGER PRIMARY KEY`
- `job_id TEXT NOT NULL`
- `module_code TEXT NOT NULL`
- `feature_code TEXT`
- `workflow TEXT`
- `legacy_status TEXT`
- `unified_status TEXT NOT NULL`
- `started_at TEXT`, `finished_at TEXT`, `duration_seconds REAL`
- `output_path_used TEXT NOT NULL`
- `period_start_used TEXT`, `period_end_used TEXT`
- `used_global_output INTEGER NOT NULL`
- `used_global_period INTEGER NOT NULL`
- `source_summary TEXT`
- `success_count`, `warning_count`, `failed_count`, `skipped_count`
- `summary_json_path`, `process_log_path`
- `error_message TEXT`
- `configuration_snapshot_hash TEXT`
- `created_at TEXT NOT NULL`

Unique: `(module_code, job_id)`.
Indexes: `(module_code, started_at DESC)`, `(unified_status, started_at DESC)`,
`(workflow, started_at DESC)`.
Retention: metadata retained according to an explicit future policy; deleting
external artifacts must update availability, not silently delete job history.

#### `job_files`

Columns: `job_file_id`, `job_pk` FK, `file_role`, `file_path`, `file_size`,
`file_hash`, `exists_at_last_check`, `recorded_at`, `last_checked_at`.

Unique: `(job_pk, file_role, file_path)`.
Index: `job_pk`, `file_hash`.
Retention: reference only; never store file BLOBs in v1.

#### `job_status_events`

Columns: `status_event_id`, `job_pk` FK, `occurred_at`, `legacy_status`,
`unified_status`, `phase`, `message`.

Index: `(job_pk, occurred_at)`.
Purpose: preserve transitions instead of overwriting only the last status.

### 7.7 Audit, import, backup, and health

#### `configuration_audit`

Columns exactly support:

- `audit_id INTEGER PRIMARY KEY`
- `changed_at TEXT NOT NULL`
- `module_code TEXT NOT NULL`
- `setting_scope TEXT NOT NULL`
- `setting_key TEXT NOT NULL`
- `old_value TEXT`
- `new_value TEXT`
- `change_source TEXT NOT NULL`
- `operator TEXT`
- `import_batch_id INTEGER` FK

Allowed `change_source`:
`Unified UI`, `Excel Import`, `Migration`, `Restore`, `Reset Default`.

Indexes: `(module_code, changed_at DESC)`, `import_batch_id`.
Retention: long-lived; redact or omit sensitive values before insert.

#### `config_import_batches`

Columns: `import_batch_id`, `module_code`, `source_file_name`,
`source_file_hash`, `import_mode`, `started_at`, `finished_at`, `status`,
`rows_read`, `rows_valid`, `rows_rejected`, `error_summary`,
`diagnostic_report_path`, `operator`.

Unique: source hash is not globally unique because re-validation is allowed.
Index: `(module_code, started_at DESC)`, `source_file_hash`.
Required in v1: Yes.

#### `backup_history`

Columns: `backup_id`, `action_type`, `source_path`, `backup_path`,
`database_hash`, `schema_version`, `started_at`, `finished_at`, `status`,
`validation_result`, `operator`, `notes`.

Allowed action types:
`BACKUP`, `RESTORE_FROM_BACKUP`, `IMPORT_EXISTING_DATABASE`,
`RESET_TO_DEFAULT`.

#### `system_health_history`

Columns: `health_check_id`, `checked_at`, `check_code`, `status`,
`message`, `details_json`.

Controlled status: `PASS`, `WARNING`, `FAIL`.
Index: `(check_code, checked_at DESC)`.
Retention: bounded; recommended 90 days or last 100 results per check, subject
to product approval.

### 7.8 Table constraint and lifecycle matrix

Unless stated otherwise, configuration rows have `created_at` and/or
`updated_at` timestamps, business columns used by an active row are NOT NULL,
optional descriptive values may be NULL, and boolean columns have a `0/1`
CHECK. Exact DDL remains a DB1 deliverable.

| Table | PK | FK | Primary unique/index rules | Timestamp and null policy | Retention | v1 |
|---|---|---|---|---|---|---:|
| `database_metadata` | `metadata_id` | None | Unique `database_uuid`; singleton check | All metadata required except `last_migrated_at` | Database lifetime | Yes |
| `global_settings` | `global_settings_id` | None | Singleton check | Output/timestamp required; period pair and operator nullable | Current row; audit preserves changes | Yes |
| `application_preferences` | `preference_key` | None | PK lookup | Value/type/update required | Current allow-listed preferences | Yes |
| `attendance_settings` | `attendance_settings_id` | None | Singleton check | Settings/update required | Current row; audit preserves changes | Yes |
| `attendance_sources` | `attendance_source_id` | None | Unique workflow/code; index workflow/active/order | Code, name, workflow, flags, timestamps required; path may be NULL only when inactive | Retain inactive masters | Yes |
| `outlook_settings` | `outlook_settings_id` | None | Singleton check | Core mailbox/transport/settings required; conditional SMTP and deadline fields nullable | Current row; audit preserves changes | Yes |
| `outlook_sender_master` | `sender_id` | None | Unique workflow/company/branch/email; sender and branch lookup indexes | Workflow/email/flags/timestamps required; NIK, names, CC and HO branch fields nullable/empty by contract | Retain inactive masters | Yes |
| `outlook_subject_rules` | `subject_rule_id` | None | Unique workflow/pattern; workflow/active index | Workflow, pattern, flag, timestamps required | Retain inactive rules | Yes |
| `outlook_attachment_rules` | `attachment_rule_id` | None | Unique workflow/extension; workflow/active index | Workflow, extension, flag, timestamps required | Retain inactive rules | Yes |
| `outlook_validation_rules` | `validation_rule_id` | None | Unique rule/workflow; workflow/active index | Code, workflow, value, flag, timestamps required | Retain inactive rules | Yes |
| `outlook_reply_templates` | `reply_template_id` | None | Unique reply code; trigger/active index | Code, recipient, trigger, body, flag, timestamps required; subject nullable only where legacy trigger permits | Retain inactive templates | Yes |
| `outlook_summary_recipients` | `recipient_id` | None | Unique type/email; type/active index | Type, email, flag, order, timestamps required | Retain inactive recipients | Yes |
| `hris_settings` | `hris_settings_id` | None | Singleton check | URL, settings and update required; click-profile path nullable when unused | Current row; audit preserves changes | Yes |
| `hris_run_controls` | `run_control_pk` | None | Unique workflow/sequence and workflow/ID; workflow/active/order index | Workflow, sequence, text ID, flag, timestamps required; description nullable | Retain inactive controls | Yes |
| `hris_assisted_steps` | `assisted_step_id` | None | Unique sequence and step name; active/order index | Contract fields, flags and timestamps required; description nullable | Retain inactive steps | Yes |
| `comparison_settings` | `comparison_settings_id` | None | Singleton check | Global flags/update required | Current row; audit preserves changes | Yes |
| `attachment_consolidation_settings` | `attachment_settings_id` | None | Singleton check | Output flag, split limit and update required | Current row; audit preserves changes | Yes |
| `job_history` | `job_pk` | None | Unique module/job ID; module/status/workflow time indexes | Identity, unified status, output resolution flags and creation required; period/result/error fields nullable by feature/outcome | Product retention policy; never silent-delete evidence references | Yes |
| `job_files` | `job_file_id` | `job_pk -> job_history` | Unique job/role/path; job/hash indexes | Job, role, path, availability and recorded time required; hash/size/check time nullable | Follows job history; stores references only | Yes |
| `job_status_events` | `status_event_id` | `job_pk -> job_history` | Job/time index | Job, event time and unified status required; legacy/phase/message nullable | Follows job history | Yes |
| `configuration_audit` | `audit_id` | `import_batch_id -> config_import_batches` | Module/time and import-batch indexes | Scope/key/source/time required; values/operator/batch nullable and redacted when sensitive | Long-lived | Yes |
| `config_import_batches` | `import_batch_id` | None | Module/time and source-hash indexes | Module/source/mode/start/status/counts required; finish/error/report/operator nullable | Long-lived diagnostic history; policy may archive old reports | Yes |
| `backup_history` | `backup_id` | None | Action/time and hash indexes | Action/source/start/status required; destination/hash/finish/result/operator/notes nullable until completion | Keep with retained backup catalogue | Yes |
| `system_health_history` | `health_check_id` | None | Check/time index | Check/time/status/message required; details JSON nullable | Proposed 90 days or last 100/check | Yes |

Foreign keys use `ON DELETE RESTRICT` for operational and audit history. Routine
configuration imports deactivate missing master/rule rows instead of deleting
them. A future approved retention task may delete a job's child records and
then its parent in one explicit transaction; schema v1 does not perform silent
cascades.

## 8. Relationships

```text
database_metadata        global_settings
         │                      │
         └──────── configuration_audit ◄── config_import_batches

attendance_settings      attendance_sources
outlook_settings         outlook_sender_master
                         outlook_subject_rules
                         outlook_attachment_rules
                         outlook_validation_rules
                         outlook_reply_templates
                         outlook_summary_recipients
hris_settings            hris_run_controls
                         hris_assisted_steps
comparison_settings      attachment_consolidation_settings

job_history ──< job_files
     │
     └────────< job_status_events

backup_history           system_health_history
```

Configuration rows do not need a shared module-settings FK. Explicit tables
give safer constraints and prevent unrelated keys from being accepted.

## 9. Unified status vocabulary

Schema v1 controlled job statuses:

```text
PENDING
VALIDATING
READY_FOR_UPLOAD
RUNNING
PAUSED
COMPLETED
COMPLETED_WITH_WARNING
FAILED
CANCELLED
NEED_REVIEW
SKIPPED
UPLOADED
```

Legacy status is always retained alongside the normalized status.

| Legacy status | Module/level | Unified status | Notes |
|---|---|---|---|
| `READY` | HRIS job | `READY_FOR_UPLOAD` | Upload plan and artifacts ready |
| `VALIDATING` | HRIS job | `VALIDATING` | Pre-browser phase |
| `RUNNING` | HRIS job | `RUNNING` | Active upload |
| `PENDING` | HRIS file | `PENDING` | Waiting in upload plan |
| `PROCESSING` | HRIS file | `RUNNING` | Current upload item |
| `INTERRUPTED` | HRIS job/file | `PAUSED` | Resume may be possible |
| `COMPLETED` | HRIS/Outlook job | `COMPLETED` | No warning |
| `COMPLETED WITH WARNING` | Outlook job | `COMPLETED_WITH_WARNING` | Normalize spaces to underscore form |
| `SUCCESS` | HRIS file | `UPLOADED` | Submission succeeded |
| `FAILED` | Any job/file | `FAILED` | Preserve failure code/message |
| `CANCELLED` | Any job | `CANCELLED` | Operator cancellation |
| `SKIPPED` | HRIS file | `SKIPPED` | Preserve reason |
| `SUCCESS` | Outlook message | `COMPLETED` | Message-level outcome, not a job status |
| `CREATED` / `FAILED` | Outlook report | `COMPLETED` / `FAILED` | Retain report substatus separately |
| `PASS` / `WARNING` | Outlook reconciliation | `COMPLETED` / `COMPLETED_WITH_WARNING` | Retain reconciliation substatus separately |
| `SKIPPED_OTHER_WORKFLOW` | Outlook message | `SKIPPED` | Expected filter outcome |
| `READY` | Attachment file | `PENDING` | Scanned and ready for consolidation |
| `SUCCESS` | Attachment file | `COMPLETED` | File produced valid output |
| `PARTIAL_SUCCESS` | Attachment file | `COMPLETED_WITH_WARNING` | Some valid output exists |
| `NO_VALID_RECORD` | Attachment file | `NEED_REVIEW` | No output accepted |
| `FAILED` | Attachment file | `FAILED` | File-level processing failure |
| `UNSUPPORTED_FORMAT`, `TEMPORARY_SKIPPED`, `HIDDEN_SYSTEM_SKIPPED`, `SYMLINK_SKIPPED`, `OUTPUT_SKIPPED` | Attachment file | `SKIPPED` | Preserve exact reason |
| `CANCELLED` | Attachment file | `CANCELLED` | Operator cancellation |
| `PAIRED` | Attendance record | `COMPLETED` | Normal in/out pair |
| `VALID_FOR_TXT` | Attendance record | `COMPLETED` | Record-level mapping |
| `VALID_WITH_WARNING` | Attendance record | `COMPLETED_WITH_WARNING` | Record-level mapping |
| `INVALID`, `SINGLE_TAP`, `MISSING_NIK`, `INVALID_CHECKTIME` | Attendance record | `NEED_REVIEW` | Do not convert into job failure |
| `DUPLICATE_REMOVED` | Attendance record | `SKIPPED` | Audit count retained |
| `MACHINE_COMPLETE_NO_REVISION`, `MACHINE_COMPLETE_REVISION_MATCH` | Comparison record | `COMPLETED` | Normal/result match |
| `MACHINE_COMPLETE_REVISION_DIFFERENT`, `MACHINE_ANOMALY_NO_REVISION`, `MACHINE_ANOMALY_REVISION_AVAILABLE`, `MACHINE_ANOMALY_REVISION_INCOMPLETE` | Comparison record | `NEED_REVIEW` | Difference or machine anomaly |
| `REVISION_ONLY`, `MACHINE_SOURCE_CONFLICT`, `MULTIPLE_REVISION_CONFLICT`, `INVALID_SOURCE_DATA` | Comparison record | `NEED_REVIEW` | Revision-only, conflict, or invalid source |

This mapping is reporting-only in DB1. Engine constants must not be replaced.

## 10. External artifact ingestion

DB1 should ingest only metadata already produced by engines:

- Attendance: job/workflow/dates/counts, MDB summaries, TXT/report paths,
  `Process.log`, and `summary.json`.
- Outlook: email counts, final/report/reconciliation status, message status,
  TXT/report/attachment references.
- HRIS: job status, progress/counts, TXT/run-control plan references,
  upload/failed/report paths.
- Comparison Result: source roots, period, counts, warnings, report/log/summary
  paths.
- Attachment Consolidation: mode, workflow, duration/counts, TXT/report/log/
  summary paths.

Adapters should consume result objects first and use `summary.json` as
recovery/import evidence. They must not parse generated Excel reports to build
routine job history.
