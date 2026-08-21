# OAS-K Database Decisions v1

Status: Sprint DB0 architecture decisions
Database implemented: No
Registry implemented: Yes, explicit HKCU service in DB3
Target implementation sprint: DB1 foundation and DB3 storage

## 1. Decision summary

| ID | Decision | Status |
|---|---|---|
| DB0-ADR-001 | Use one active SQLite database in a local writable data root | Accepted |
| DB0-ADR-002 | Keep operational evidence as external files; store summaries and references | Accepted |
| DB0-ADR-003 | Use explicit relational tables; limit key-value storage to simple UI preferences | Accepted |
| DB0-ADR-004 | Keep Excel for import, export, templates, backup, and legacy fallback | Accepted |
| DB0-ADR-005 | Make global output and global period independent, with per-run overrides | Accepted |
| DB0-ADR-006 | Use sequential schema migrations; never require database deletion for an upgrade | Accepted |
| DB0-ADR-007 | Start with SQLite rollback journal (`DELETE`), not WAL | Accepted |
| DB0-ADR-008 | Do not store passwords, tokens, or credentials in configuration or audit tables | Accepted |
| DB0-ADR-009 | Use explicit safe database action terminology; never use “Replace Database” | Accepted |
| DB0-ADR-010 | Preserve a configuration audit trail while redacting sensitive values | Accepted |

## 2. ADR-001: active database and data root

### Decision

The target default data root is:

```text
D:\OAS-K\Data
├── database
│   └── OAS-K.db
├── backup
├── output
├── logs
└── diagnostics
```

The active database should reside on a local writable volume. If `D:` is
missing or not writable, a later storage workflow lets the user select another
local folder.

Only these pointers are planned under
`HKEY_CURRENT_USER\Software\OTO Finance\OAS-K`:

- `DataRoot`
- `DatabasePath`

No JSON pointer is placed beside the executable. Registry discovery,
permissions, explicit-session fallback, and controlled relocation are
implemented by the DB3 storage service.

### Rationale

- A per-machine local database matches the current single-user desktop model.
- Local storage reduces SQLite locking and network interruption risks.
- `HKEY_CURRENT_USER` does not normally require administrator access.
- Separating the pointer from the executable supports read-only installation
  locations.

### Consequences

- DB1 must accept an explicit database path and must not assume Registry exists.
- A network share may contain exported files or backups, but is not the default
  home of the active database.
- `OAS-K.db` is not created during DB0.

## 3. ADR-002: external evidence remains external

SQLite is the source for active configuration, operational summaries, status
history, file references, audit events, backup history, and health results.
It does not replace:

- HRIS TXT input;
- Attendance TXT;
- Excel reports and comparison workbooks;
- `Process.log`;
- `summary.json`;
- Outlook attachments;
- Attachment Consolidation outputs.

`job_files` stores a path, file role, size, optional hash, and availability
state. `job_history` stores bounded summaries and the actual output/period
values used. Raw Attendance rows and attachment bytes are excluded from schema
v1. BLOB is therefore not needed.

This keeps the database small, preserves existing evidence, and avoids changing
stable output formats. Missing external files are reported by System Health or
history views; their absence does not corrupt the configuration database.

## 4. ADR-003: relational schema over generic settings

Settings with known contracts use explicit tables and typed columns:

- `attendance_settings`, `attendance_sources`;
- `outlook_settings` and Outlook rule/master tables;
- `hris_settings`, `hris_run_controls`, `hris_assisted_steps`;
- `comparison_settings`, `attachment_consolidation_settings`.

A generic `module_settings` table is excluded because it would move type,
required-field, uniqueness, and relationship validation into application code.
`application_preferences` is the only limited key-value table; it is for
non-business UI preferences whose keys are controlled by the application.

Reference sheets containing prose are retained in workbook templates and
legacy exports. They do not justify empty `attendance_reference` or
`hris_reference` tables in schema v1.

## 5. ADR-004: Excel remains a supported boundary

SQLite becomes the planned active configuration source only after a phased
migration. Excel remains available for:

1. import;
2. export of editable current configuration;
3. blank templates and guide material;
4. bulk editing;
5. independent backup;
6. legacy-reader fallback during transition.

The current Excel readers are not deleted in DB1. Database adapters should
produce the same normalized configuration structures expected by current
consumers before an engine is switched.

### Export designs

| Action | Purpose | Required characteristics |
|---|---|---|
| Export Configuration Template | New/manual preparation | Empty business rows, correct headers, per-cell validation, guide/reference content, safe examples only |
| Export Current Configuration | Edit and re-import active SQLite settings | Lossless text IDs, multiline templates, active/inactive rows, valid workbook contract |
| Export Legacy-Compatible Configuration | Temporary support for old readers | Exact legacy sheet names, columns, parameter names, boolean/workflow spellings, and necessary compatibility defaults |

Export is a DB1-or-later design item only; no exporter is implemented in DB0.

## 6. ADR-005: global values and per-run overrides

`global_settings` holds one global output root and one optional global period:

- `output_root`;
- `period_start`;
- `period_end`.

Global output and global period are selected independently. A future module UI
may expose `Use Global Output & Period` as a convenient combined control, but
the request model must carry two independent flags:

- `use_global_output`;
- `use_global_period`.

The resolved values are copied to each job:

- `output_path_used`;
- `period_start_used`;
- `period_end_used`;
- `used_global_output`;
- `used_global_period`.

A per-run override never changes `global_settings`. Modules without a period,
such as Attachment Consolidation, leave the period fields NULL and set
`used_global_period = 0`. This decision avoids forcing irrelevant dates onto
utilities.

## 7. ADR-006: schema versioning and migrations

### Version sources

- `database_metadata.schema_version` is the application-readable version.
- `database_metadata.application_version` records the last writing OAS-K
  version.
- `created_at`, `updated_at`, and `last_migrated_at` use ISO 8601.
- SQLite `PRAGMA user_version` mirrors `schema_version` as an integrity check.

### Migration policy

1. Versions are positive sequential integers.
2. Every migration has a known `from_version` and `to_version`.
3. The active file is backed up before a schema migration.
4. Migration runs in one transaction where SQLite permits it.
5. Foreign keys and integrity are checked before commit.
6. Metadata and `user_version` are updated only after all migration steps
   succeed.
7. Any error triggers rollback and leaves the pre-migration database active.
8. Database deletion is never the normal upgrade mechanism.
9. A newer unsupported schema is opened read-only or rejected with a clear
   diagnostic; it is never silently downgraded.

Migration scripts, runner, and database creation are outside DB0.

## 8. ADR-007: SQLite connection policy

The initial recommendation for a local, single-user desktop application is:

```sql
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;
```

Every connection closes safely through a context-managed boundary. Writes are
short, transactional, and never held open while a workbook is being parsed or
while an engine performs a long-running job.

WAL is not selected initially because:

- the expected write concurrency is low;
- it introduces companion `-wal` and `-shm` files;
- copying only the main file while a WAL transaction is active can produce an
  incomplete backup;
- network/shared folders and some office endpoint controls make WAL behavior
  less predictable.

WAL may be reconsidered only after measurement demonstrates concurrent-read
pressure on a guaranteed local data root. Backups should use the SQLite backup
API, not an unmanaged copy of an open database.

## 9. ADR-008: security and sensitive values

- Passwords, access tokens, browser credentials, and credential material are
  not database settings.
- Outlook mailbox addresses and SMTP host/port are operational configuration,
  not passwords; they still receive access-controlled display and audit
  redaction where appropriate.
- `configuration_audit` must not store secrets. If a future setting is marked
  sensitive, audit stores a marker such as `[REDACTED]`, never old/new content.
- Diagnostic reports must avoid attachment bodies, email bodies, credentials,
  and unnecessary personal data.
- Database permissions should be restricted to the current user where the
  Windows environment permits it.
- An imported database is never executed or made active before structural and
  integrity validation.

## 10. ADR-009: database action terminology

These are the only approved user-facing actions:

| Action | Meaning |
|---|---|
| Backup Database | Create a validated point-in-time copy using the SQLite backup API |
| Restore from Backup | Activate a healthy backup copy after validation and safety backup |
| Import Existing Database | Bring a healthy database from another machine/location into the active data root |
| Reset to Default | Create a fresh schema/default database without old history, while retaining a safety backup |
| Validate Database | Run path, metadata, schema, foreign-key, and integrity checks without changing active data |
| Open Database Folder | Open the folder containing the active database |
| Change Data Location | Safely copy and validate the whole managed data root, then change its pointer |

The phrase **Replace Database** is prohibited because it hides whether an action
is a restore, an import, or a reset and therefore hides different validation
and recovery behavior.

## 11. ADR-010: configuration audit trail

`configuration_audit` records:

- `audit_id`;
- `changed_at`;
- `module`;
- `setting_scope`;
- `setting_key`;
- `old_value`;
- `new_value`;
- `change_source`;
- `operator`;
- `import_batch_id`.

Allowed initial `change_source` values are:

- `Unified UI`;
- `Excel Import`;
- `Migration`;
- `Restore`;
- `Reset Default`.

One logical import creates one `config_import_batches` row and links every
configuration change made by that import. Audit insertion is part of the same
transaction as the configuration change. Rollback therefore removes both the
new values and their uncommitted audit events. Restore activity is also
recorded in `backup_history`; it does not manufacture row-by-row differences
when the source database already contains its own history.

## 12. Excel import pipeline

```text
Excel
  -> Reader
  -> Mapping
  -> Validation
  -> Preview
  -> Transaction
  -> Commit or Rollback
```

### 12.1 Preflight and reader

Before any database write, the importer:

1. copies or opens the workbook read-only;
2. computes a SHA-256 hash;
3. identifies the expected module and canonical workbook contract;
4. inventories sheets, headers, data types, validations, and duplicate keys;
5. rejects encrypted, unreadable, unrelated, or structurally unsafe files;
6. parses values without relying on Excel formulas or recalculation;
7. preserves text identifiers such as HRIS `001` and `02`.

The reader produces a neutral import model. It must not call an engine and must
not mutate the workbook.

### 12.2 Mapping and validation

Validation is parameter- and field-based rather than copying defective
workbook cell ranges. It checks:

- required sheets and headers;
- required values for active rows;
- controlled workflows and statuses;
- unique source/rule/sequence keys;
- boolean and numeric bounds;
- ISO-convertible dates and ordered periods;
- local path syntax and context-appropriate existence/writability;
- email, mailbox, SMTP, URL, and placeholder rules;
- HRIS assisted-step name/action/source/method contracts;
- multiline reply template preservation;
- development/mock data and dangerous outbound-send values.

Warnings do not silently become approval. Production-sensitive findings such
as a local mock HRIS URL, test email, `Auto_Reply_Enabled=TRUE`, or
`Send_Mode=SEND` require explicit preview confirmation.

### 12.3 Preview

Preview is read-only and shows:

- module and source hash;
- rows to insert/update/deactivate;
- global-value candidates and conflicts;
- normalized values alongside source values;
- fields ignored because no current consumer exists;
- duplicate/typo repair decisions;
- warnings, blocking errors, and mock/development findings;
- whether the mode is Replace Module Configuration or Merge Reference/Master
  Data.

Attendance's duplicate `Payroll_Periode_From` and the two identical Outlook
workbooks are explicitly reported. They are never silently resolved.

### 12.4 Transaction and atomicity

Import is atomic per module:

1. insert `config_import_batches` with status `VALIDATING`;
2. complete parsing and preview outside the write transaction;
3. begin an immediate, short transaction after operator confirmation;
4. revalidate the active schema version;
5. apply the selected module change;
6. insert audit rows;
7. mark the batch `COMPLETED`;
8. commit.

Any constraint, audit, schema, or write failure rolls back the entire module
change. The application then records a failure diagnostic outside the rolled
back transaction when possible. A failed import leaves active configuration
unchanged.

### 12.5 Import modes

**Replace Module Configuration** replaces only the selected module's active
configuration tables. It does not replace global settings without a separate
explicit selection in preview, and it never replaces the database.

**Merge Reference/Master Data** is allowed only where stable business keys and
clear merge semantics exist, initially:

- Attendance sources by `(workflow, source_code)`;
- Outlook sender master by its approved composite identity;
- Outlook rules/templates by their documented unique keys;
- HRIS run controls by `(workflow, run_control_id)`;
- HRIS assisted steps by canonical step name.

Unknown existing rows are not deleted in merge mode unless the preview provides
an explicit deactivation operation. Prose `Reference` sheets are not merged
into SQLite.

## 13. Module-specific migration rules

### Attendance

- Read period start from legacy General row 8 and period end from row 9.
- Report row 9's duplicate key and map it as the logical end date.
- Resolve `General.OutputFolder` against `Output.Output_Root`; the current
  reader gives General precedence.
- Do not activate unused formatting, output-subpath, or job-folder parameters.
- Missing MDB files block an active source but may warn for inactive templates.

### HRIS

- Treat `OAS-K_HRIS_Configuration.pre_assisted_backup.xlsx` as a backup, not a
  second active configuration.
- Preserve every Run Control ID as TEXT.
- Reject duplicate sequences or canonical assisted step names.
- Do not activate unused retry, resume, browser, folder-name, or report switches.
- The local mock URL and fixed dates require confirmation and should not become
  safe defaults.

### Outlook Revisi

- Prefer `OAS-K_Outlook-Revisi_Configuration.xlsx`; report the identical
  `Configuration1` file as a duplicate.
- Validate by parameter name, not the workbook's shifted validation ranges.
- Reject active sender rows that have no email instead of silently skipping
  them.
- Preserve multiline bodies and validate all placeholders.
- Confirm the exact mailbox/reply-from addresses.
- Never activate automatic outbound sending from an import without explicit
  preview confirmation.

### Utilities

- Comparison Result stores run inputs in history; only genuinely reusable
  defaults belong in `comparison_settings`.
- Attachment Consolidation uses output but no period.
- `TXT_Max_Lines` may be copied from Outlook during initial migration and then
  becomes an independently managed utility setting.
- Empty Merge TXT/Excel modules do not receive speculative schema.

## 14. Backup, restore, import, reset, and relocation

### Backup Database

1. Validate the active path and database metadata.
2. Use the SQLite backup API to a new timestamped file in `backup`.
3. Run `integrity_check` on the copy.
4. Compute size and SHA-256.
5. Record `backup_history` only after success.
6. Apply a documented retention policy; never delete the only healthy backup.

### Restore from Backup

1. Select a backup without changing active state.
2. Validate file type, metadata, application compatibility, schema support,
   `integrity_check`, and foreign keys in staging.
3. Create a safety backup of the active database.
4. Close all active connections and stop new jobs.
5. Copy the validated candidate to a temporary file in the active database
   folder.
6. Atomically switch files where the filesystem permits.
7. Reopen, validate, and record the restore.
8. If activation validation fails, restore the safety backup.

### Import Existing Database

The same staging and validation rules apply, but the source may come from
another machine or folder and is not assumed to be a trusted OAS-K backup.
Unsupported newer schemas are rejected. Older supported schemas are copied to
staging and migrated there before activation. The original import file is never
modified.

### Reset to Default

1. Require explicit operator confirmation.
2. Create a safety backup.
3. Create and validate a fresh database in staging using the current schema and
   safe defaults.
4. Activate it atomically.
5. Keep old evidence files and the safety backup.

Reset does not delete or overwrite external TXT, reports, logs, summaries, or
attachments.

### Change Data Location

A later storage sprint copies the managed root to a writable staging folder,
validates the database and required directories, atomically changes the
Registry pointer, and retains a recovery pointer until the new location opens
successfully. It does not place an active SQLite database on a network share by
default.

## 15. Phased migration and fallback

| Phase | Active read | Write behavior | Exit condition |
|---|---|---|---|
| DB1 foundation | Excel readers remain authoritative | Create/test schema and importer only in isolated test paths | Schema, migrations, repository API, and import preview pass tests |
| Dual-read validation | Excel remains default; SQLite adapter runs comparison | No engine output change | Normalized Excel and SQLite structures match on approved fixtures |
| Module opt-in | Selected module reads SQLite with Excel fallback | Configuration changes audit to SQLite | Module regression and fallback tests pass |
| SQLite primary | SQLite is active source; legacy Excel export remains | Excel is import/export/fallback | All modules migrated and observed |
| Legacy retirement review | SQLite primary | Reader removal considered separately | Explicit business approval; not automatic |

At every phase, only the selected engine may run. A configuration-source
failure must fail closed or use an explicit compatible fallback; it must not
start a different engine or silently change business rules.

## 16. Risk register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Attendance duplicate period key loses start date | High | High | Position-aware importer, preview repair, ordered-period validation |
| R2 | Wrong Outlook duplicate file is selected | High | Medium | Canonical resolution, hashes, duplicate warning |
| R3 | Development paths, dates, mock URL, or test emails become active | High | High | Environment-sensitive preview, explicit confirmation, safe defaults |
| R4 | Outlook import sends real automatic replies | Medium | Critical | Default DRAFT/auto-reply off for fresh DB, explicit outbound confirmation, no engine call during import |
| R5 | HRIS IDs lose leading zeros | Medium | High | Parse/store/export as TEXT; round-trip tests |
| R6 | Multiline template or placeholder corruption | Medium | High | Exact TEXT preservation, newline and placeholder tests |
| R7 | Unused workbook keys become misleading runtime switches | High | Medium | Consumer-backed mapping; exclude phantom settings from schema v1 |
| R8 | Global output conflicts across three workbooks | High | Medium | Show candidates and precedence in preview; select once explicitly |
| R9 | Global period semantics differ by module | Medium | High | ISO dates, module adapters, independent flags, per-run resolved history |
| R10 | Long engine job holds a database write lock | Medium | High | Short transactions; status updates open/close independently; busy timeout |
| R11 | WAL companion files are omitted from backup | Low after decision | High | Use DELETE initially and SQLite backup API |
| R12 | Active DB is placed on an unreliable network share | Medium | High | Local writable default; reject/warn network paths; documented relocation |
| R13 | Restore/import activates a corrupt or incompatible file | Low | Critical | Staging, metadata/version checks, integrity/foreign-key checks, safety backup, rollback |
| R14 | Database or diagnostics expose personal/sensitive data | Medium | High | No credentials, bounded summaries, audit redaction, file permissions |
| R15 | External evidence path becomes stale | Medium | Medium | `job_files` availability checks, hashes where useful, System Health warnings |
| R16 | Removing Excel readers breaks standalone modules | Medium | High | Phased dual-read, adapter comparison, keep fallback until explicit retirement |
| R17 | Schema migration partly applies | Low | Critical | Backup first, transaction, version update last, post-migration validation |
| R18 | Reset unintentionally deletes history/evidence | Low | Critical | Clear terminology, safety backup, staging activation, external evidence untouched |

## 17. Recommended Sprint DB1 scope

DB1 should implement only the database foundation:

1. schema v1 DDL and sequential migration contract;
2. connection factory with required PRAGMAs and safe close;
3. typed repository interfaces for configuration and operational history;
4. isolated test-database fixtures in temporary directories;
5. read-only Excel import readers, mapping, validation, and preview;
6. transactional per-module import with audit records;
7. integrity, foreign-key, leading-zero, multiline-template, rollback, and
   duplicate-key tests;
8. backup API service tests against temporary databases.

DB1 should not yet:

- switch an engine or GUI to SQLite;
- delete or modify the current Excel readers;
- implement Registry discovery;
- relocate the data root;
- change existing output naming or formats;
- package an executable;
- create an active project `OAS-K.db` without separate user approval.

This boundary provides enough tested infrastructure for a later controlled
dual-read migration without mixing storage changes with engine behavior.

## 18. DB2B workbook authoring decision

Decision: use the already-installed `openpyxl` dependency for DB2B workbook
authoring and structural validation.

Rationale:

- the preferred `@oai/artifact-tool` runtime was re-audited and unavailable;
- the approved DB2B instruction explicitly authorizes `openpyxl` as fallback;
- no new dependency, Office installation, COM automation, or macro is needed;
- existing DB2A readers already use openpyxl in safe read-only mode;
- generation is bounded to OAS-K configuration workbooks and validated after
  every save.

Consequences:

- generated files are formula-free `.xlsx` workbooks;
- exact sheet order, headers, validations, TEXT IDs, and safety properties are
  enforced by code and tests;
- export remains read-only against SQLite and never activates configuration;
- visual inspection in desktop Excel remains a release-review activity, while
  structural QA is automated and repeatable.

## 19. DB4 recovery activation decision

Decision: all Restore from Backup, Import Existing Database, and Reset to
Default operations use explicit confirmation, a validated staging candidate,
a pre-operation SQLite Backup API safety copy when an active database is
readable, post-activation validation, and rollback before Registry activation.

Application-data backups use standard ZIP plus JSON manifest. Archive entries
are traversal-checked and the staged database hash must match the manifest.
Recorder profiles are included; output is excluded by default.

The existing `backup_history` and `configuration_audit` tables remain the
recovery audit boundary. No schema migration, pointer JSON, auto-restore,
source deletion, engine/GUI integration, scheduler, or executable build is
part of DB4.
