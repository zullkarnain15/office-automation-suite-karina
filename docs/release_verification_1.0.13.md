# OAS-K 1.0.13 Release Verification

Verified on 30 September 2026 for production core database schema 4 and
Attendance & OT analytics schema 5.

## Release artifacts

- Executable: `dist/release/v1.0.13/application/OAS-K.exe`
  - Size: 85,934,767 bytes
  - SHA-256: `fac2cd1ba8cdd9a605aa52d240e56eccd4fc56fb0cb1cb30a8861975f9794dcf`
- Update package: `dist/release/v1.0.13/OAS-K_Update_v1.0.13.zip`
  - Size: 85,257,759 bytes
  - SHA-256: `e0259932de96c9d7daa7082e67ec7abcd4219d76633dc2dc46b76abe6c845593`
- Embedded updater: `dist/updater/OAS-K-Updater.exe`
  - Size: 10,032,834 bytes
  - SHA-256: `c1a6b1283079e786b40fd3b37f7f553156e3fe36505f51f219c6a7e770929be7`

## Database gate

- Core production schema accepted: 4
- Core target schema: 4
- `migration_required`: `false`
- Minimum current application version: 1.0.12
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

## Automated verification

- Full suite: 980 passed
- Update, startup migration, Attendance & OT, and UI release gate:
  129 passed
- Scoped Ruff checks for changed release/UI files: PASS
- Python compilation check: PASS
- Frozen archive contains Attendance & OT modules and the rebuilt updater: PASS
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
