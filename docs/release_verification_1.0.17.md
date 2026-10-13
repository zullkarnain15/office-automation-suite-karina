# OAS-K 1.0.17 Release Verification

Date: 8 October 2026
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

- Mandatory update and startup-migration suites: 57 passed.
- Full regression suite: 1026 passed.
- Changed-file Ruff checks: PASS.
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
- Package size: 88,892,122 bytes
- Package SHA-256:
  `4643f5346ff7c2b577f7ade4cf5c366328dac1b788cf628a9a3455daeeb6a36d`
- Executable: `dist/release/v1.0.17/application/OAS-K.exe`
- Executable size: 89,572,120 bytes
- Executable SHA-256:
  `bd33cbc0eeb418a2c1505dd3a16cd5f6ac8feb32ec8cc6783c6114ef1c554a79`
- Updater SHA-256:
  `c5e961bdd7e713fdac23528c6d2d84c5d2021e9d3734b280b8d9e8aad46a99ac`

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
