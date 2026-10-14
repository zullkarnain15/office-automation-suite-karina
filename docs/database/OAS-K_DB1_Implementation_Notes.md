# OAS-K DB1 Implementation Notes

Status: Implemented and tested
Schema version: 1
Production database created: No

## 1. Scope

Sprint DB1 implements only the reusable SQLite foundation under
`shared/database`. It does not connect an Attendance, Outlook Revisi, HRIS, or
Utilities engine to SQLite. It does not replace the Excel readers, use the
Registry, select an active production path, change output formats, or implement
restore/import/reset workflows.

The implementation uses Python's built-in `sqlite3` module and adds no
dependency.

## 2. Schema v1

`shared/database/schema/v1.sql` creates the 24 tables approved in DB0:

1. `database_metadata`
2. `global_settings`
3. `application_preferences`
4. `attendance_settings`
5. `attendance_sources`
6. `outlook_settings`
7. `outlook_sender_master`
8. `outlook_subject_rules`
9. `outlook_attachment_rules`
10. `outlook_validation_rules`
11. `outlook_reply_templates`
12. `outlook_summary_recipients`
13. `hris_settings`
14. `hris_run_controls`
15. `hris_assisted_steps`
16. `comparison_settings`
17. `attachment_consolidation_settings`
18. `job_history`
19. `job_files`
20. `job_status_events`
21. `configuration_audit`
22. `config_import_batches`
23. `backup_history`
24. `system_health_history`

No `module_settings`, generic `utilities_settings`, Merge TXT/Excel setting
table, raw Attendance table, or attachment BLOB table was added.

The initial schema transaction inserts only the required metadata singleton.
Module configuration remains empty until a future explicit import or repository
write. `global_settings` may therefore have zero rows as a safe unconfigured
state; the validator reports this as a warning. The first valid save creates
the singleton row.

## 3. Connection policy

`SQLiteConnectionFactory.connect()`:

- accepts `Path` or string;
- creates a parent directory only with `create_parent=True`;
- uses `sqlite3.Row`;
- enables `foreign_keys`;
- applies a 5,000 ms busy timeout;
- uses rollback journal mode `DELETE`;
- uses `synchronous=FULL` for writable connections;
- supports read-only URI mode;
- commits a clean context and rolls back an exceptional context;
- always closes the connection;
- never stores a global connection.

`DELETE` journal mode is intentionally conservative for a primarily
single-user Windows desktop application. It avoids persistent `-wal` and
`-shm` companion files and is easier to relocate or inspect. Backup still uses
the SQLite backup API rather than copying an open file.

## 4. Schema and migration APIs

`SchemaManager` provides:

- `initialize_database(path, application_version, create_parent=False)`
- `is_initialized(path)`
- `get_schema_version(path)`
- `verify_required_tables(path)`
- `ensure_compatible_schema(path, expected_version=1)`

Initialization executes each SQL statement and inserts metadata inside one
`BEGIN IMMEDIATE` transaction. A failed statement rolls back both schema
objects and metadata. Existing valid v1 data is not recreated or reset.

`MigrationManager` provides:

- `get_current_version()`
- `get_target_version()`
- `requires_migration()`
- `migrate()`

Version 1 is a validated no-op. No v1-to-v2 migration exists. A newer database
raises `SchemaMismatchError`; an older database without a registered step
raises `MigrationError`. Neither condition deletes or resets the file.

## 5. Validation

`DatabaseValidator.validate()` returns `DatabaseValidationResult`, including:

- file existence/readability;
- SQLite header state;
- `integrity_check`;
- `foreign_key_check`;
- schema version;
- missing required tables;
- missing required indexes;
- warnings and errors.

Metadata and `PRAGMA user_version` must agree. An initialized database with no
global settings row remains structurally valid but receives an unconfigured
warning.

`validate_or_raise()` converts an invalid result into
`DatabaseValidationError` for service boundaries that require a healthy
database.

## 6. Backup

`BackupManager.create_backup()`:

1. validates the source;
2. refuses the source path as destination;
3. refuses overwrite unless explicitly enabled;
4. invokes `sqlite3.Connection.backup()`;
5. closes both connections;
6. validates the completed backup;
7. returns file size, SHA-256, schema version, timestamp, and validation result.

Restore, import-existing-database, reset-default, active-path selection, and
Registry pointer management are outside DB1.

## 7. Typed repositories

Repositories accept a caller-owned `sqlite3.Connection`. They never hold a
global connection and do not independently commit. Multiple repository writes
inside one connection-factory context therefore form one atomic unit.

Implemented repositories:

- `MetadataRepository`
- `GlobalSettingsRepository`
- `JobRepository`
- `AuditRepository`
- `BackupHistoryRepository`

`GlobalSettingsRepository` validates complete ISO date pairs and does not
create an output folder.

`JobRepository` supports:

- `create_job`
- `update_job_status`
- `finish_job`
- `add_job_file`
- `get_job_by_id`
- `list_recent_jobs`

Only the DB0 Unified status vocabulary is accepted. Legacy status remains an
optional reference and no engine constant is changed.

## 8. Typed models and import-preview contract

Implemented persistence models:

- `DatabaseMetadata`
- `GlobalSettings`
- `JobHistoryRecord`
- `JobFileRecord`
- `ConfigurationAuditRecord`
- `BackupHistoryRecord`
- `DatabaseValidationResult`
- `BackupResult`

The read-only `shared/database/importing` contract provides
`ConfigImportIssue`, `ConfigImportPreview`, and `ConfigImportBatch`. It does not
open a workbook or write configuration. The actual Excel importer remains a
future sprint.

## 9. Tests

Database tests live under `tests/database` and use pytest temporary
directories. They cover:

- package import isolation;
- exact 24-table creation;
- metadata and `user_version`;
- required PRAGMAs;
- explicit parent creation;
- repeat initialization without data loss;
- initialization rollback;
- schema mismatch without reset;
- v1 migration no-op;
- integrity/foreign-key validation;
- missing table and index detection;
- invalid SQLite input;
- global settings round-trip and invalid periods;
- job lifecycle, status events, and file references;
- audit and backup-history writes;
- multi-repository rollback;
- HRIS leading-zero IDs;
- Outlook multiline template preservation;
- foreign-key enforcement;
- SQLite backup validation and source preservation;
- no engine, GUI, or Registry import/use;
- no database artifact in the project root.

Current DB1 result:

```text
31 passed
Ruff: all checks passed
```

## 10. Manual test tool

`tools/database_test/create_test_database.py` requires an explicit `--output`
path. It refuses paths under `D:\OAS-K\Data`, refuses implicit overwrite, and
creates parent folders only with `--create-parent`.

Example:

```powershell
python tools/database_test/create_test_database.py `
  --output "$env:TEMP\OAS-K-DB1\test.db" `
  --create-parent
```

An optional explicit `--backup` path exercises the validated backup API.

## 11. Known technical debt and DB2 boundary

- No configuration table repositories exist yet beyond global settings.
- No Excel workbook importer or transactional import batch service exists.
- No operational result adapter writes current engine results to job history.
- No retention executor exists for history/health records.
- No restore/import/reset or data-location service exists.
- Email/URL/path validation remains an importer/service responsibility beyond
  relational checks.
- Schema migrations have a contract but no version transition yet.

Recommended DB2 scope is read-only Excel import parsing, field-level mapping,
validation, preview, and one atomic module import service with audit rows. DB2
must continue using temporary/test database paths until production storage and
Registry behavior receive separate approval.
