# OAS-K 1.0.14 Release Verification

Verified on 30 September 2026 for production core database schema 4 and
Attendance & OT analytics schema 5.

## Release artifacts

- Executable: `dist/release/v1.0.14/application/OAS-K.exe`
  - Size: 85,935,737 bytes
  - SHA-256: `f0c59a3bc5ac2e9d91808ab2e9aef75e5b7987a1d629758ff48662429b027fe9`
- Update package: `dist/release/v1.0.14/OAS-K_Update_v1.0.14.zip`
  - Size: 85,258,930 bytes
  - SHA-256: `4b05ba8a80bfa9ac55910af577c0dfcc7524e4dfce85b7fd9cf5b1d358b59a67`
- Embedded updater: `dist/updater/OAS-K-Updater.exe`
  - Size: 10,032,834 bytes
  - SHA-256: `c1a6b1283079e786b40fd3b37f7f553156e3fe36505f51f219c6a7e770929be7`

## Database gate

- Current production application accepted: 1.0.13
- Target application: 1.0.14
- Core production schema accepted: 4
- Core target schema: 4
- `migration_required`: `false`
- Attendance & OT analytics schema: 5, unchanged
- Pre-update core backup validation: PASS
- Core database dump before and after preparation/health check: identical
- Analytics schema 5 startup acceptance: PASS
- Analytics schema 5 fixture data before and after startup: identical
- Existing output and recorder profile files: preserved
- `ApplicationUpdateService.prepare_update()`: PASS
- `PostUpdateHealthCheck`: SUCCESS

The Attendance & OT analytics database is separate from the OAS-K core database.
Its internal schema 5 does not change the release manifest's core schema 4 range.

## Dashboard performance verification

- Dashboard trend uses aggregate SQL and does not load Detail Data pages.
- UI Dashboard requests only the two displayed rankings.
- Default reporting API remains compatible for Export Excel and existing callers.
- Filter choices are reused until analytics data is changed.
- Refresh, duplicate deletion, purge, and reset invalidate the filter cache.

## Automated verification

- Full suite: 982 passed
- Targeted Attendance & OT reporting/UI tests: 31 passed
- Scoped Ruff checks for changed release/UI files: PASS
- Python compilation check: PASS
- Frozen archive contains Attendance & OT modules and the embedded updater: PASS
- Frozen OAS-K Tk shell opened and closed normally: PASS
- ZIP and frozen archive prohibited-data scan: PASS

The only test warning is the intentional duplicate-ZIP-entry rejection fixture.

## Package contents

The application-only ZIP contains exactly:

- `application/`
- `application/OAS-K.exe`
- `manifest.json`
- `release_notes.txt`
- `checksums.sha256`

No database, MDB, Data Root, log, output, backup, or recorder profile is included.
