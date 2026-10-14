# OAS-K 1.0.17 Release Verification

Date: 14 October 2026
Status: PASS

## Production database gate

- Core production schema: 4
- Core target schema: 4
- Core migration required: false
- Attendance & OT production schema: 9
- Attendance & OT target schema: 9
- Attendance & OT migration required: false
- Minimum supported current application: 1.0.16

The production source versions were confirmed as OAS-K 1.0.16, core schema 4,
and Attendance & OT schema 9. Isolated databases at those schema levels were
validated with `PRAGMA quick_check` during the release gate.

The application-only package was validated against an isolated schema-4 core
database. Update preparation created and validated a pre-update backup, the
post-update health check completed successfully, and existing core records,
output files, and recorder profiles were preserved.

An isolated schema-9 Attendance & OT database containing a production fixture
was also passed through update preparation and post-update health checking.
The analytics database remained schema 9, no analytics migration was run, its
integrity check passed, and the existing attendance fixture was unchanged.

## Automated validation

- Update, startup-migration, and Attendance & OT database suites: 115 passed.
- Full UI suite: 344 passed.
- PyInstaller updater build: PASS.
- PyInstaller application build: PASS.
- Frozen Tk application shell smoke test: PASS.
- Embedded updater checksum verification: PASS.
- Native python-calamine extension verification: PASS.
- ZIP checksum and internal checksums: PASS.
- Prohibited Data Root/database/log/output/backup/profile content: none.
- Unrelated ZIP assets bundled into the executable: none.

## Artifacts

- Package: `dist/release/v1.0.17/OAS-K_Update_v1.0.17.zip`
- Package size: 99,921,268 bytes
- Package SHA-256:
  `9bedf521cf7f6d820a267247dfd53b942ada647ecae08595110284236846bd60`
- Executable: `dist/release/v1.0.17/application/OAS-K.exe`
- Executable size: 100,637,999 bytes
- Executable SHA-256:
  `055d094efa9ab914989cc293dd4ef34588d3dccb6d91c15016e8daacbe32b6c1`
- Updater SHA-256:
  `cb9dab1662102e490b4b2c2ec81bab9924165b8133f03de8364133787347265c`

## Package manifest

```json
{
  "version": "1.0.17",
  "minimum_current_version": "1.0.16",
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
