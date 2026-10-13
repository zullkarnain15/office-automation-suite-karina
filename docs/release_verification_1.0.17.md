# OAS-K 1.0.17 Release Verification

Date: 13 October 2026
Status: PASS

## Production database gate

- Core production schema: 4
- Core target schema: 4
- Core migration required: false
- Attendance & OT production schema: 9
- Attendance & OT target schema: 9
- Attendance & OT migration required: false
- Minimum supported current application: 1.0.15

The active production databases were inspected read-only before packaging.
Both metadata schema and SQLite `user_version` were 4 for the core database
and 9 for Attendance & OT. `PRAGMA quick_check` returned `ok` for both.

The application-only package was validated against an isolated schema-4 core
database. Update preparation created and validated a pre-update backup, the
post-update health check completed successfully, and existing core records,
output files, and recorder profiles were preserved.

An isolated schema-9 Attendance & OT database containing a production fixture
was also passed through update preparation and post-update health checking.
The analytics database remained schema 9, no analytics migration was run, its
integrity check passed, and the existing attendance fixture was unchanged.

## Automated validation

- Mandatory update, startup-migration, and Attendance & OT suites: 70 passed.
- PyInstaller updater build: PASS.
- PyInstaller application build: PASS.
- Frozen Tk application shell smoke test: PASS.
- Embedded updater checksum verification: PASS.
- Bundled private Attendance & OT fonts: PASS.
- Native python-calamine extension verification: PASS.
- ZIP checksum and internal checksums: PASS.
- Prohibited Data Root/database/log/output/backup/profile content: none.
- Unrelated ZIP assets bundled into the executable: none.

## Artifacts

- Package: `dist/release/v1.0.17/OAS-K_Update_v1.0.17.zip`
- Package size: 99,898,162 bytes
- Package SHA-256:
  `b13c6de5357314ce866879e48d2482c5c31d57c34a84269657e6bc19fcb17929`
- Executable: `dist/release/v1.0.17/application/OAS-K.exe`
- Executable size: 100,615,266 bytes
- Executable SHA-256:
  `cde5b0a9d81d04728139d9d2bf31373fa4825d75fad1d04e52daa9f3373d5fba`
- Updater SHA-256:
  `819eac5df20dae8dedc256063d25e356137ab95643eaa51a59a499fa80491c7e`

## Package manifest

```json
{
  "version": "1.0.17",
  "minimum_current_version": "1.0.15",
  "package_type": "application_only",
  "database_schema_from": 4,
  "database_schema_to": 4,
  "migration_required": false,
  "entry_executable": "OAS-K.exe"
}
```

The package contains only `application/OAS-K.exe`, `manifest.json`,
`release_notes.txt`, and checksum metadata. It does not contain a core or
analytics database, MDB file, Data Root, logs, output, backup, recorder
profiles, or unrelated source ZIP files.
