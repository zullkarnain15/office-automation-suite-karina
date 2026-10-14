# OAS-K DB3 Storage Notes

Status: Implemented
Schema: v1 unchanged (24 tables)
Engine/GUI integration: Not implemented
Production bootstrap executed: No

## 1. Scope

DB3 implements a service-only Windows storage foundation. Importing
`shared.storage` does not create a folder, database, Registry key, JSON
pointer, GUI, or engine process.

The package is split into constants, typed models, path resolution, read-only
validation, explicit bootstrap, fake/HKCU Registry backends, startup
resolution, recorder-profile validation, and controlled relocation.

Restore from Backup, Reset to Default, and full Import Existing Database
activation are not implemented in DB3.

## 2. Data Root contract

The preferred Data Root remains `D:\OAS-K\Data`:

```text
<DataRoot>
├── database
│   └── OAS-K.db
├── recorder_profiles
│   └── hris
├── backup
├── output
├── logs
└── diagnostics
```

All names are centralized in `shared/storage/constants.py`. The suggested
fallback `%USERPROFILE%\Documents\OAS-K\Data` is returned only as a UI
suggestion; it is never selected or created automatically.

Data Root and Global Output Root remain separate. Folder `output` is created
as storage structure, while `global_settings` remains empty after bootstrap.

## 3. Registry pointer

The only persisted pointer is:

`HKEY_CURRENT_USER\Software\OTO Finance\OAS-K`

Values:

- `DataRoot`
- `DatabasePath`

The Windows backend uses standard-library `winreg` and HKCU only. It does not
use HKLM or elevation. No backend is instantiated and no Registry operation
occurs during import. Automated tests use `FakeRegistryBackend`.

When Registry is unavailable, bootstrap returns a valid database plus a
warning so the caller can use the explicit path for the current session. No
fallback JSON pointer is created.

## 4. Startup resolution

`resolve_startup_storage()` is non-mutating and returns:

- `READY`
- `AVAILABLE_NOT_REGISTERED`
- `INITIAL_SETUP_REQUIRED`
- `RECOVERY_REQUIRED`
- `REGISTRY_UNAVAILABLE`
- `INVALID_LOCATION`

It never creates, resets, imports, or writes a Registry value.

## 5. Explicit bootstrap

`StorageBootstrapService.initialize_storage()` must be called explicitly. It:

1. validates a local writable target;
2. creates the standard directories;
3. creates schema v1 only when `OAS-K.db` is absent;
4. validates new or existing databases;
5. never overwrites/resets an invalid database;
6. writes HKCU only after database validation;
7. treats Registry failure as a session-fallback warning;
8. does not insert global settings or import Excel.

Repeated bootstrap reuses an existing valid database.

## 6. Recorder profiles

HRIS recorder JSON lives under
`<DataRoot>\recorder_profiles\hris`. Persisted references are relative, for
example `recorder_profiles\hris\ho_upload_profile.json`.

Validation rejects absolute persisted references, traversal, paths outside
`recorder_profiles`, and non-JSON extensions. A missing file is allowed with a
warning. Existing content must be readable JSON with an object root. HRIS
business-step validation and schema metadata are intentionally deferred.

## 7. Controlled relocation

`DataLocationManager.change_data_location()` defaults to:

- copy the database through DB1 `BackupManager` (SQLite backup API);
- copy valid recorder-profile JSON;
- do not copy output or logs;
- never delete the source.

The target and copied database are validated before Registry activation.
Existing target databases require explicit overwrite permission. Failure keeps
the old pointer and rolls back temporary/new target database files when safe.

## 8. Candidate validation

`validate_existing_database_candidate()` exposes DB1 validation only. It does
not copy, migrate, or activate a candidate. Full Import Existing Database is
DB4 scope.

## 9. Manual CLI

```text
py tools/storage_test/storage_bootstrap_cli.py ^
  --data-root "D:\OAS-K-Test\Data" --validate-only
```

Actions: `--validate-only`, `--show-layout`, `--initialize`, and
`--validate-profile RELATIVE_JSON_PATH`.

`--data-root` is mandatory. Registry persistence is off by default.
`--write-registry` works only with `--initialize` and also requires
`--confirm-registry-write`.

## 10. Safety boundary

DB3 did not create the production Data Root automatically, touch real Registry
during tests, create pointer JSON, change schema v1, switch an engine/reader,
change GUI/workbooks, implement Restore/Reset/full Import Existing, or build
an executable.

DB4 should implement staged backup/restore/import workflows and activation
auditing. Engine integration remains separately gated.
