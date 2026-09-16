# OAS-K DB2 Import and Export Notes

Status: DB2 importer, template, and exporters completed
Database schema: v1 unchanged
Production database created: No

## 1. Importer architecture

The DB2 importer is split into small boundaries:

1. `workbook_detector` identifies a workbook from sheet signatures.
2. `workbook_reader` reads cells with `read_only=True`, `data_only=False`, and
   `keep_links=False`.
3. `normalizer` converts booleans, workflows, dates, paths, and text IDs.
4. Legacy or unified mappers produce schema-v1 table rows.
5. Modular validation produces structured issues.
6. `PreviewBuilder` compares proposed rows to current SQLite rows.
7. `ImportTransactionService` performs an explicit atomic module commit.
8. `ConfigImportService` exposes preview and commit without implicit writes.

No existing Excel reader, engine, GUI, or workbook was changed.

## 2. Workbook detection

Supported identities:

- `ATTENDANCE_LEGACY`
- `OUTLOOK_REVISI_LEGACY`
- `HRIS_LEGACY`
- `OAS_K_UNIFIED`
- `UNKNOWN`
- `AMBIGUOUS`

Detection is based on required sheet sets. Filename is retained as evidence but
does not determine identity. Each detection includes a binary SHA-256 and a
normalized-content hash. The normalized hash detects the two identical Outlook
workbooks as duplicate configuration evidence.

An older HRIS workbook without `Assisted_Steps` is recognized as HRIS legacy
and receives `HRIS_ASSISTED_STEPS_MISSING`.

## 3. Mapping

### Global

Legacy module values become global candidates:

- Attendance `OutputFolder`/`Output_Root`
- Attendance period rows 8 and 9
- Outlook `Output_Root` and derived full-month `Payroll_Period`
- HRIS `Folder_Upload_Path`, `Start_Date`, and `End_Date`

Different candidates produce `GLOBAL_OUTPUT_CONFLICT` or
`GLOBAL_PERIOD_CONFLICT`. A caller must rebuild preview with an explicit
`global_resolution`; resolved conflicts produce `GLOBAL_CONFLICT_RESOLVED`.

### Attendance

- `General` runtime-backed values -> `attendance_settings`
- `MDB_HO`, `MDB_Branch` -> `attendance_sources`
- `Output` -> global candidate only
- `Reference` and unused format/subpath keys -> not active SQLite settings

The duplicated `Payroll_Periode_From` is reported and follows the DB0
position-aware mapping only with confirmation.

### Outlook Revisi

- `General` -> `outlook_settings` and global candidates
- sender sheets -> `outlook_sender_master`
- subject, attachment, and validation sheets -> their relational rule tables
- reply templates -> `outlook_reply_templates`
- PIC/SPV recipient lists -> `outlook_summary_recipients`

Allowed extensions are split into one normalized row per extension. Multiline
template bodies retain newlines and braces.

### HRIS

- `General`, `Browser`, `Upload` -> consumer-backed `hris_settings`
- `Run_Control` -> `hris_run_controls`
- `Assisted_Steps` -> `hris_assisted_steps`
- `Reference` -> not imported

Run Control IDs remain TEXT. Numeric cells without a preservable zero format
produce `RUN_CONTROL_ID_TEXT_FORMAT_LOST`.

### Utilities

The unified contract maps only `comparison_settings` and
`attachment_consolidation_settings`. No Merge TXT/Excel table or speculative
field is introduced.

## 4. Normalization and validation

Accepted boolean inputs are `TRUE`, `FALSE`, `YES`, `NO`, `Y`, `N`, `1`, and
`0`. SQLite output is INTEGER `1/0`.

Workflow values normalize to `HO` or `BRANCH`; rule workflows may additionally
use `ALL`. ISO dates and typed Excel dates are accepted. Ambiguous text dates
are rejected unless a documented legacy order is supplied by a mapper.

Validation covers:

- split limits, required active MDB paths, and source duplicates;
- mailbox format, sender/rule duplicates, attachment extensions, and reply
  placeholders;
- HRIS URL structure, text IDs, workflow/sequence uniqueness, and assisted
  action/source/method sets;
- Utilities TXT split limit;
- global conflicts and complete date pairs.

## 5. Issue and confirmation rules

Important issue codes include:

- `ATTENDANCE_DUPLICATE_PERIOD_KEY`
- `DEVELOPMENT_PATH_DETECTED`
- `SAMPLE_MDB_DETECTED`
- `DUPLICATE_WORKBOOK_DETECTED`
- `OUTLOOK_AUTOMATIC_SEND_ENABLED`
- `TEST_SENDER_DETECTED`
- `UNKNOWN_REPLY_TEMPLATE_PLACEHOLDER`
- `HRIS_MOCK_URL_DETECTED`
- `HRIS_ASSISTED_STEPS_MISSING`
- `RUN_CONTROL_ID_TEXT_FORMAT_LOST`
- `FIXED_TESTING_DATE_DETECTED`
- `GLOBAL_OUTPUT_CONFLICT`
- `GLOBAL_PERIOD_CONFLICT`
- `GLOBAL_CONFLICT_RESOLVED`
- `WORKBOOK_UNKNOWN`
- `WORKBOOK_AMBIGUOUS`

Errors block commit. Critical operational values such as live Outlook
automatic send and a mock HRIS URL require explicit confirmation but remain
previewable. Any delete or warning marked confirmation-required also blocks an
unconfirmed commit.

## 6. Preview lifecycle

Preview:

- opens no persistent connection;
- writes no configuration, batch, audit, or job rows;
- reports `INSERT`, `UPDATE`, `DELETE`, and `UNCHANGED`;
- exposes destructive changes;
- calculates a configuration snapshot hash;
- includes mapped module payloads only as immutable dataclass state.

Commit rejects a stale preview if the current configuration snapshot differs.
Timestamp and auto-generated primary-key columns are excluded from meaningful
round-trip comparison.

## 7. Transaction and audit behavior

The default boundary is one SQLite transaction per selected module. `GLOBAL`
is a separate unit using `UPDATE_GLOBAL_SETTINGS`.

Within one module transaction:

1. insert the import batch in `RUNNING`;
2. replace or merge only that module's approved tables;
3. insert `configuration_audit` rows with source `Excel Import`;
4. mark the batch `COMPLETED`;
5. commit.

Any error rolls back configuration, audit, and the running batch. A separate
short transaction records a `FAILED` batch after rollback. Another module's
tables are not deleted or replaced.

Audit values are parameterized and fields whose names indicate password,
secret, token, or credential are redacted.

## 8. Unified template contract

The agreed unified workbook structure remains:

1. `Guide`
2. `Global_Settings`
3. `Attendance_Settings`
4. `Attendance_Sources`
5. `Outlook_Settings`
6. `Outlook_Sender_Master`
7. `Outlook_Subject_Rules`
8. `Outlook_Attachment_Rules`
9. `Outlook_Validation_Rules`
10. `Outlook_Reply_Templates`
11. `Outlook_Summary_Recipients`
12. `HRIS_Settings`
13. `HRIS_Run_Controls`
14. `HRIS_Assisted_Steps`
15. `Comparison_Settings`
16. `Attachment_Consolidation`

Singleton setting sheets use the operator-friendly vertical columns
`setting_key`, `setting_value`, `required`, and `description`. Relational
tables use schema-v1 field names so the workbook does not introduce
speculative fields. The mapper also retains support for the original DB2A
horizontal singleton representation.

The official workbook is:

`config/templates/OAS-K_Configuration_Template.xlsx`

It has light professional styling, Indonesian guidance, required-value
markers, wrapped text, useful column widths, freeze panes, AutoFilters, and
data validation for booleans, workflows, active flags, and constrained HRIS
assisted-step fields. `run_control_id` is formatted as TEXT through row 500.
There are no formulas, macros, external links, or secret defaults.

Nama tab worksheet untuk konfigurasi fitur Attachment Consolidation adalah
`Attachment_Consolidation` (24 karakter), sehingga seluruh nama sheet unified
memenuhi batas maksimum Excel 31 karakter. Nama konseptual bisnis tetap
“Attachment Consolidation Settings”, dan nama table SQLite tetap
`attachment_consolidation_settings`.

## 9. Export status

The public DB2B API is exposed from `shared.database.exporting`:

- `build_configuration_template`
- `export_current_configuration`
- `export_attendance_legacy`
- `export_outlook_legacy`
- `export_hris_legacy`
- `validate_configuration_workbook`

Current configuration export validates the database first, uses a read-only
SQLite connection, selects only the approved configuration columns, writes to
a temporary sibling workbook, validates it, and atomically replaces the
requested output. Existing output and parent-directory creation both require
explicit options.

The exported Guide includes only non-secret metadata: export timestamp,
schema version, application version, and database UUID. A deny-list prevents
future password, secret, token, credential, or API-key columns from being
silently exported.

All three legacy exporters produce workbooks detected and parsed by the
existing DB2A readers. Outlook legacy stores only `MM-YYYY`; therefore a
global period that is not exactly one full calendar month raises
`LegacyExportUnsupportedError` instead of losing date precision.

The acceptance roundtrip is covered:

1. initialize a temporary schema-v1 database;
2. build and fill a unified workbook;
3. preview and explicitly commit all five configuration units;
4. export the current configuration;
5. detect and preview the exported workbook;
6. assert every comparison operation is `UNCHANGED`.

## 10. Tests

Importer and exporter tests use only pytest temporary databases and temporary
workbook fixtures. Coverage includes:

- all three actual legacy identities;
- unknown and ambiguous workbooks;
- read-only hash preservation;
- boolean/workflow/date normalization;
- ambiguous date rejection;
- HRIS leading zeros;
- Outlook multiline templates;
- duplicate workbook and period findings;
- high-risk Outlook and HRIS warnings;
- global conflicts and explicit resolution;
- preview no-write behavior;
- insert and unchanged comparisons;
- invalid and unconfirmed preview rejection;
- stale preview rejection;
- separate global commit;
- atomic Attendance commit;
- module isolation;
- audit and batch history;
- rollback with failure history;
- audit redaction.
- exact 16-sheet order and headers;
- formulas, macros, external links, freeze panes, AutoFilters, and wrapping;
- data-validation ranges and required markers;
- TEXT preservation for `001`, `02`, and `3`;
- multiline Outlook reply content;
- explicit overwrite and parent-directory behavior;
- corrupted workbook rejection;
- current-export metadata and secret exclusion;
- full import -> commit -> export -> preview `UNCHANGED` roundtrip;
- Attendance, Outlook, and HRIS legacy reader compatibility;
- loss-aware Outlook legacy period rejection.

## 11. DB2B authoring decision and acceptance

The preferred `@oai/artifact-tool` runtime was re-audited and was not
installed. DB2B's approved fallback rule explicitly allows `openpyxl`, which
was already a project dependency, so no package was added. No LibreOffice,
Excel COM automation, pandas export, VBA, or macro route was used.

Structural QA is implemented in
`shared/database/exporting/workbook_validator.py` and can be run manually with:

`python tools/database_test/inspect_configuration_workbook.py config/templates/OAS-K_Configuration_Template.xlsx`

The validator checks openability, exact sheets, formulas, macros, links,
headers, freeze panes, AutoFilters, TEXT formatting, wrapped reply content,
and unified detection. Automated tests perform the same checks on fresh
workbooks and corrupted fixtures.

DB2 is accepted at source and automated-test level. No production database,
Registry value, UI integration, existing legacy workbook, engine, or
executable was created or changed. DB3 is intentionally not started.

## 12. DB2C worksheet-name compatibility

DB2C mengganti nama tab unified
`Attachment_Consolidation_Settings` (33 karakter) menjadi
`Attachment_Consolidation` (24 karakter). Perubahan hanya berlaku pada nama
worksheet; nama fitur konseptual “Attachment Consolidation Settings” dan table
SQLite `attachment_consolidation_settings` tidak berubah.

Kontrak constants, detector, mapper, builder, current exporter, validator,
roundtrip tests, dan template resmi telah diperbarui secara konsisten.
Validator kini menolak setiap workbook unified yang memiliki nama sheet lebih
panjang dari 31 karakter. DB2 tetap final `COMPLETED`, dan DB3 belum dimulai.

SHA-256 template resmi hasil regenerasi DB2C:
`95A695A6405A668ADDEE644254CEE0A080BD209781D21EF8B64C2BDB09DD3B21`.
