# OAS-K DB4 Recovery Notes

- Status: COMPLETED
- Schema: v1 unchanged (24 tables)
- Engine/GUI integration: Not implemented
- Production Registry/Data Root used by tests: No
- Executable build: Not performed

## 1. Scope

DB4 adds explicit service-layer workflows for Backup Database, Backup
Application Data, Restore from Backup, Import Existing Database, Reset to
Default, and read-only Recovery Mode recommendations.

The implementation lives under `shared/recovery`. Importing it does not open a
database, create a Data Root, write Registry values, start an engine, or open a
GUI.

## 2. Candidate validation

Every candidate is checked before activation for:

- file existence and readability;
- SQLite header;
- `PRAGMA integrity_check`;
- enabled foreign keys and `PRAGMA foreign_key_check`;
- schema version 1 compatibility;
- metadata singleton;
- all 24 required tables and required indexes.

Validation is read-only. Newer/incompatible schemas and incomplete candidates
are rejected.

## 3. Backup Database

`DatabaseBackupService` delegates file creation to DB1 `BackupManager`, which
uses the SQLite Backup API. Default files use
`OAS-K_YYYY-MM-DD_HHMMSS.db`; collisions receive a numeric suffix unless the
caller explicitly requests overwrite.

The result is validated and reports SHA-256, size, schema version, and
`backup_history` ID. Controlled reasons are `MANUAL`, `BEFORE_RESTORE`,
`BEFORE_IMPORT`, `BEFORE_RESET`, `BEFORE_RELOCATION`, and `BEFORE_UPGRADE`.

## 4. Backup Application Data

The application-data format is a standard ZIP containing:

- `database/OAS-K.db`, produced with the SQLite Backup API;
- `recorder_profiles/hris/*.json`;
- `manifest.json`;
- logs and diagnostics only when explicitly requested.

`output`, `build`, `dist`, temporary files, and caches are excluded by default.
The manifest records format/application/schema versions, timestamp, source Data
Root, database archive path/hash, included/excluded paths, and profile count.
The source Data Root is operational provenance and may expose a local folder
name; archive access must therefore follow the same protection as the database.
Recorder-profile JSON is validated as an object and backups are rejected when
credential-like keys are detected.

Archive validation rejects unreadable ZIPs, missing manifest/database, absolute
entries, traversal, symlinks, hash mismatch, and an invalid database.

## 5. Restore from Backup

Restore accepts a validated `.db` or official application-data `.zip`. It
requires `confirm=True`, preserves the source, backs up a readable active
database, stages a private candidate below
`<DataRoot>/diagnostics/recovery_staging/<operation_id>`, validates before and
after activation, optionally merges restored recorder profiles, records
history/audit, and only then updates Registry when explicitly requested.

Activation moves the previous active database to an operation-local rollback
path before an atomic `os.replace` of the staged candidate. Any activation,
final-validation, audit, profile, or Registry failure restores the prior active
database. Staging cleanup is best-effort on both success and failure.

## 6. Import Existing Database

Import requires confirmation and rejects the active database as its own source.
The source may be on removable/download/network storage, but it is never used
in place. It is copied to recovery staging, validated again, and activated only
at `<DataRoot>/database/OAS-K.db`. The source is never modified or deleted.

## 7. Reset to Default

Reset requires `confirm=True`, first backs up a readable current database,
creates a fresh schema-v1 candidate in staging, validates and activates it, and
records the operation in the new database. Global settings and prior history
are empty in the new candidate before the reset operation is audited. No Excel
file is imported. Recorder profiles are preserved by default and removed only
when the caller explicitly sets `preserve_recorder_profiles=False`.

## 8. Backup failure and force

Restore/import/reset stop when a readable active database cannot be backed up.
The typed requests expose `force_without_prebackup`; using it is an explicit
caller decision and adds a warning to the result/audit. A missing active
database does not pretend that a safety backup exists.

## 9. Registry

DB4 reuses the DB3 `StorageRegistryService`. Registry persistence is off by
default. When requested, the pointer is written only after active database
validation and audit. A write failure is not reported as success and triggers
database rollback. No JSON pointer fallback exists.

Automated tests inject `FakeRegistryBackend`; they neither instantiate a
production Registry backend nor create `D:\OAS-K\Data`.

## 10. Audit and history

The existing `backup_history` and `configuration_audit` tables are used; no
table or migration was added. Recovery identifiers use file names rather than
full external paths. Database SHA-256 values, success/failure, source type,
operator, and bounded warnings are recorded. Operator values containing common
secret markers are redacted.

Import uses the existing controlled audit source `Migration`, restore uses
`Restore`, and reset uses `Reset Default`, matching schema-v1 constraints.

## 11. Recovery Mode

`RecoveryService.assess()` is side-effect-free. It maps startup, candidate,
backup availability, and Registry validity to statuses including `HEALTHY`,
`DATABASE_MISSING`, `DATABASE_INVALID`, `SCHEMA_INCOMPATIBLE`,
`REGISTRY_POINTER_INVALID`, `DATA_ROOT_UNAVAILABLE`, `BACKUP_AVAILABLE`, and
`NO_BACKUP_AVAILABLE`.

Recommendations include restore last/selected backup, import, reset, select
Data Root, open diagnostics, and cancel. The service has no method that
executes those actions and startup performs no automatic restore.

## 12. Manual CLI

`tools/recovery_test/recovery_cli.py` provides:

- `backup-db`
- `backup-app-data`
- `validate-candidate`
- `restore`
- `import-db`
- `reset-default`
- `recovery-status`

Every command requires `--data-root`; no production path is defaulted.
Restore/import require `--confirm`, reset requires `--confirm-reset`, and
production Registry writes require both `--write-registry` and
`--confirm-registry-write`. The documented emergency bypass is exposed only as
the explicit `--force-without-prebackup` flag.

## 13. Boundaries and technical debt

DB4 does not connect SQLite to engines or GUI, replace the old Configuration
Reader, remove legacy workbooks, schedule backups, auto-restore at startup,
delete sources/Data Roots, add a dependency, alter schema v1, or build an EXE.

Deferred to the Unified UI sprint:

- operator-facing selection and confirmation dialogs;
- progress/cancellation presentation;
- archive retention policy and scheduled backups;
- desktop Excel/Registry/manual disaster-recovery acceptance;
- protection/ACL policy for backups containing local provenance;
- coordinated engine shutdown before Windows file activation.
