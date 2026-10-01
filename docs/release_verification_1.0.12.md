# OAS-K 1.0.12 Release Verification

Verified on 29 September 2026 for production core database schema 4 and
Attendance & OT analytics schema 5.

## Release artifacts

- Executable: `dist/release/v1.0.12/application/OAS-K.exe`
  - Size: 85,922,424 bytes
  - SHA-256: `8ea264cf62577a6425258b334275d8d816fa56c072a1785a2925511dfdef59ea`
- Update package: `dist/release/v1.0.12/OAS-K_Update_v1.0.12.zip`
  - Size: 85,245,749 bytes
  - SHA-256: `3e48f1c9ff746b2702ee0bd700ef8cb4c23e7779cc2c977f805fdceddab50b2f`
- Embedded updater: `dist/updater/OAS-K-Updater.exe`
  - Size: 10,032,986 bytes
  - SHA-256: `d2262d71a306c8c9d04f0f3862e93da8d2cacb80c9e043a4db17e73a975736f6`

## Database gate

- Core production schema accepted: 4
- Core target schema: 4
- `migration_required`: `false`
- Minimum current application version: 1.0.11
- Attendance & OT analytics schema: 5, unchanged
- Pre-update backup validation: PASS
- Core database dump before and after preparation/health check: identical
- Existing output and recorder profile files: preserved
- `ApplicationUpdateService.prepare_update()`: PASS
- `PostUpdateHealthCheck`: SUCCESS

The Attendance & OT analytics database is separate from the OAS-K core database.
Its internal schema 5 does not change the release manifest's core schema 4 range.

## Automated verification

- Full suite: 974 passed, 1 skipped
- Update, startup migration, Attendance & OT, and UI release gate:
  123 passed, 1 skipped
- Ruff checks: PASS
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
