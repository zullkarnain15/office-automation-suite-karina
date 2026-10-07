# OAS-K 1.0.15 Release Verification

Verified on 1 October 2026 for production Core OAS-K database schema 4 and
Attendance & OT analytics database schema 5.

## Release artifacts

- Executable: `dist/release/v1.0.15/application/OAS-K.exe`
  - Size: 86,235,100 bytes
  - SHA-256: `5fe8ba0644d1f149c70d0281346d99c704a2121f615b4f55090be7edda59b391`
- Update package: `dist/release/v1.0.15/OAS-K_Update_v1.0.15.zip`
  - Size: 85,556,540 bytes
  - SHA-256: `2138cf20550b66601d31c231b62336d6012119d5ca5fbfdb5e1323b4d767792f`
- Embedded updater: `dist/updater/OAS-K-Updater.exe`
  - Size: 10,032,834 bytes
  - SHA-256: `c1a6b1283079e786b40fd3b37f7f553156e3fe36505f51f219c6a7e770929be7`

## Database gate

- Minimum current application: 1.0.14
- Target application: 1.0.15
- Core production schema accepted: 4
- Core target schema: 4
- Manifest `database_schema_from`: 4
- Manifest `database_schema_to`: 4
- Manifest `migration_required`: `false`
- Attendance & OT production schema accepted: 5
- Attendance & OT target schema: 9
- Attendance & OT migration path: 5 -> 6 -> 7 -> 8 -> 9
- Verified analytics backup before v6, v7, v8, and v9: PASS
- Existing Attendance & OT source and transaction rows preserved: PASS
- Incremental `source_file_registry` backfill: PASS
- Core pre-update backup validation: PASS
- Core database data preservation: PASS
- `ApplicationUpdateService.prepare_update()`: PASS
- `PostUpdateHealthCheck`: SUCCESS

The release manifest declares the Core OAS-K database compatibility range.
Attendance & OT uses a separate analytics database and performs its own
versioned, backed-up migration when the module initializes.

## Automated verification

- Required update/startup/analytics gate: 99 passed
- Full suite: 995 passed, 1 skipped
- Scoped Ruff and Python compilation checks: PASS
- Frozen archive contains the current Attendance & OT modules: PASS
- Embedded updater checksum: PASS
- Frozen OAS-K Tk shell opened and closed normally: PASS
- ZIP and frozen archive prohibited-data scan: PASS
- Final release verifier: PASS without traceback

The single pytest warning is the intentional duplicate-ZIP-entry rejection
fixture. PyInstaller reported optional, platform-specific imports; the frozen
application shell and required modules were verified successfully.

## Package contents

The application-only ZIP contains exactly:

- `application/`
- `application/OAS-K.exe`
- `manifest.json`
- `release_notes.txt`
- `checksums.sha256`

No database, MDB, Data Root, log, output, backup, or recorder profile is
included in the update package.
