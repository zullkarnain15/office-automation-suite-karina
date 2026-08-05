# OAS-K Application Update

## Overview

OAS-K supports manual, application-only updates. The application package is
selected and staged from Settings, then a standalone updater process applies the
staged application after OAS-K closes gracefully. The package never replaces
the Data Root or carries a database file, but the new application may run a
versioned database migration after the application files are replaced.

Automatic download, GitHub API, token storage, and Data Root replacement are
not part of this update flow.

## Folder Layout

Application Root contains `OAS-K.exe`, assets, and runtime files. Data Root
contains `database/OAS-K.db`, `recorder_profiles`, `logs`, `output`, `backup`,
and `update`.

Update state is stored under:

```text
<DataRoot>/update/transactions/<transaction_id>/transaction.json
<DataRoot>/update/staging/v<version>/application
<DataRoot>/update/rollback/<transaction_id>/application
<DataRoot>/update/logs/update_<transaction_id>.log
<DataRoot>/update/runtime/<updater_version>/updater
```

## Lifecycle

```text
STAGED
-> APPLY_REQUESTED
-> WAITING_FOR_SHUTDOWN
-> BACKING_UP_APPLICATION
-> APPLYING
-> APPLICATION_REPLACED
-> STARTING_NEW_APPLICATION
-> HEALTHCHECK_PENDING
-> SUCCESS
```

Failure after replacement requests rollback:

```text
ROLLBACK_REQUESTED
-> ROLLBACK_IN_PROGRESS
-> ROLLED_BACK
```

Terminal statuses are `SUCCESS`, `ROLLED_BACK`, `FAILED`, and `CANCELLED`.

## Health Check

The new application starts with:

```text
OAS-K.exe --post-update --update-transaction <transaction.json>
```

It validates the target version, Application Root, and Data Root. It then finds
the database belonging to the transaction Data Root, creates a pre-migration
backup when the schema is old, runs every registered migration in sequence, and
validates database integrity and schema compatibility. Logger write access and
a lightweight UI-shell construction path are also checked when enabled. A
successful run writes `healthcheck_success.json` atomically.

If database migration or validation fails, the health check fails and the
application updater requests application rollback. The pre-update and
pre-migration database backups remain available for recovery; the updater never
silently replaces the production database.

## Release Database Gate

Before packaging a release:

1. Record the current production schema and the new app's `SCHEMA_VERSION`.
2. Confirm every sequential migration script exists between those versions.
3. Declare the supported schema in `manifest.json` using
   `database_schema_from`, `database_schema_to`, and `migration_required`.
4. Validate the package against the actual old schema, not only a newly created
   development database.
5. Run a temporary Data Root smoke test through prepare, backup, migration,
   post-update health check, and final database validation.
6. Verify existing production rows survive and any newly required table or row
   is present after migration.

Required automated checks:

```powershell
python -m pytest tests/update tests/database/test_startup_migration.py -q
```

The release is blocked if the package reports an unsupported active schema, a
migration step is missing, backup fails, database integrity fails, or the final
schema does not equal the app's `SCHEMA_VERSION`.

## Rollback

Before replacement, the updater copies the old Application Root to
`<DataRoot>/update/rollback/<transaction_id>/application`. If launch or health
check fails, the updater moves the failed application to diagnostics and restores
the rollback copy. It then starts:

```text
OAS-K.exe --post-rollback --update-transaction <transaction.json>
```

The database, active configuration, recorder profiles, logs, output, and backup
folders are not replaced.

## Startup Recovery

Normal startup can inspect non-terminal transactions. Ambiguous states such as
`APPLICATION_REPLACED` or `HEALTHCHECK_PENDING` should recommend restoring the
previous application rather than attempting a complex resume.

## Updater Exit Codes

```text
0  success
10 invalid transaction
11 old process timeout
12 application backup failed
13 replacement failed
14 new application launch failed
15 health check failed
16 rollback succeeded after update failure
17 rollback failed
18 unexpected error
```

## Build Updater

Do not build on production machines unless an updater EXE build is explicitly
needed. Build command:

```powershell
py tools\build_updater.py
```

Dry-run command preview:

```powershell
py tools\build_updater.py --dry-run
```

Expected output is `dist\updater\OAS-K-Updater.exe`.

## Test

Run isolated automated tests:

```powershell
py -m pytest tests/update -q
py -m pytest tests/update tests/storage tests/recovery tests/ui/settings tests/ui/services/test_task_and_recovery_services.py -q
```

Manual simulated update should use a temporary Application Root and Data Root:

1. Create dummy current app with entry executable.
2. Prepare staged app under `<DataRoot>/update/staging/vX/application`.
3. Create a transaction with `UpdateTransactionStore`.
4. Run `py -m updater.main --transaction <transaction.json>`.
5. Verify `SUCCESS` for a marker-writing new app.
6. Repeat with a crashing new app and verify `ROLLED_BACK`.

## Limitations

The updater does not perform automatic download, GitHub API calls, Windows
Service integration, Task Scheduler integration, elevation, or cleanup beyond
STAGED cancellation. Database migrations are sequential and versioned; a
release cannot skip an unregistered schema step.
