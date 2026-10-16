# OAS-K 1.0.18 Release Verification

Date: 16 October 2026
Status: PASS

## Production database gate

- Core production schema: 4
- Core target schema: 4
- Core migration required: false
- Attendance & OT production schema: 9
- Attendance & OT target schema: 9
- Attendance & OT migration required: false
- Finger Monitoring production schema: 6
- Finger Monitoring target schema: 6
- Finger Monitoring migration required: false
- Minimum supported current application: 1.0.17

The active production databases were inspected read-only before packaging. The
core, Attendance & OT, and Finger Monitoring databases passed
`PRAGMA quick_check` and matched the source schema versions.

The application-only package was validated against an isolated schema-4 core
database. Update preparation created and validated a pre-update backup, the
post-update health check completed successfully, and existing core records,
output files, and recorder profiles were preserved.

Isolated schema-9 Attendance & OT and schema-6 Finger Monitoring databases
containing production-like fixtures were also passed through update preparation
and post-update health checking. Both module databases stayed at their current
schema versions, passed integrity checks, and preserved their existing records.

## Automated validation

- Update and startup-migration suites: 57 passed.
- Full automated test suite: 1,122 passed.
- PyInstaller updater build: PASS.
- PyInstaller application build: PASS.
- Frozen Tk application shell smoke test: PASS.
- Embedded updater checksum verification: PASS.
- Native python-calamine extension verification: PASS.
- ZIP checksum and internal checksums: PASS.
- Prohibited Data Root/database/MDB/log/output/backup/profile content: none.

## Artifacts

- Package: `dist/release/v1.0.18/OAS-K_Update_v1.0.18.zip`
- Package size: 99,969,286 bytes
- Package SHA-256:
  `e04f8efd44ec0c14cc0e1024b3bef137a7de2c9fda4b9795f870b9d9b6775d96`
- Executable: `dist/release/v1.0.18/application/OAS-K.exe`
- Executable size: 100,685,685 bytes
- Executable SHA-256:
  `407bfe0d2f98a2ea55bb1996a70773b51f77bdcb9c4e44b7f684400affa096ea`
- Updater SHA-256:
  `446e78a93509077c5c452d631036a69c548fe18cf4e20e2de19d185d93d428b4`

## Package manifest

```json
{
  "version": "1.0.18",
  "minimum_current_version": "1.0.17",
  "package_type": "application_only",
  "database_schema_from": 4,
  "database_schema_to": 4,
  "migration_required": false,
  "entry_executable": "OAS-K.exe"
}
```

The package contains only `application/OAS-K.exe`, `manifest.json`,
`release_notes.txt`, and checksum metadata. It does not contain a core,
Attendance & OT, or Finger Monitoring database; an MDB file; Data Root; logs;
output; backup; recorder profiles; or unrelated source ZIP files.
