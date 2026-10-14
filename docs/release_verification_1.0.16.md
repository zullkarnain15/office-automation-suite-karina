# OAS-K 1.0.16 Release Verification

Date: 7 October 2026
Status: PASS

## Production database gate

- Core production schema: 4
- Core target schema: 4
- Core migration required: false
- Attendance & OT production schema: 9
- Attendance & OT target schema: 9
- Attendance & OT migration required: false

The application-only package was validated against a schema-4 core database.
The update preparation created and validated a pre-update backup, the
post-update health check completed successfully, and existing core records,
output files, and recorder profiles were preserved.

An isolated schema-9 Attendance & OT database containing a production fixture
was also passed through update preparation and post-update health checking.
The analytics database remained schema 9, no migration backup was created, its
integrity check passed, and the existing attendance fixture was unchanged.

## Automated validation

- Mandatory update and startup-migration suites: 57 passed.
- Full regression suite: 1015 passed, 1 skipped.
- Attendance & OT release regression: 100 passed, 1 skipped.
- Full UI regression: 331 passed.
- PyInstaller build: PASS.
- Frozen Tk application shell smoke test: PASS.
- Embedded updater checksum verification: PASS.
- Native python-calamine extension verification: PASS.
- ZIP checksum and internal checksums: PASS.
- Prohibited Data Root/database/log/output/backup/profile content: none.

## Artifacts

- Package: `dist/release/v1.0.16/OAS-K_Update_v1.0.16.zip`
- Package size: 86,349,755 bytes
- Package SHA-256:
  `39c2f89c081706915d2cf53ce27d3eec54adce3e1d3d55c49762489ed1fbde93`
- Executable: `dist/release/v1.0.16/application/OAS-K.exe`
- Executable size: 87,028,141 bytes
- Executable SHA-256:
  `5755fd5a4f52a2b165e3db83094af9c87a15475527f2576e611fa74637a0de37`
- Updater SHA-256:
  `4baa803c06422a7b9cfd0a2845fa00850523aa90d1b65d7fcaf3217f0979e4d3`

## Package manifest

```json
{
  "version": "1.0.16",
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
analytics database, MDB file, Data Root, logs, output, backup, or recorder
profiles.
