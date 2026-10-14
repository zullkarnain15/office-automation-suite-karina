# OAS-K 1.0.11 Release Verification

Verified on 29 September 2026 for production database schema 4.

## Release artifacts

- Executable: `dist/release/v1.0.11/application/OAS-K.exe`
  - Size: 85,906,552 bytes
  - SHA-256: `c5d3978a7281abfab77ff2899c1f017805bb02764381e873f5e4040e87a9b7b6`
- Update package: `dist/release/v1.0.11/OAS-K_Update_v1.0.11.zip`
  - Size: 85,229,653 bytes
  - SHA-256: `f5142afdef2e3c44e343422015709168c672ef99f67fd8cfc3d5b17befcab9e9`
- Embedded updater: `dist/updater/OAS-K-Updater.exe`
  - Size: 10,032,588 bytes
  - SHA-256: `eeffe55b36c4e3c70465b9993c4cc756aa5a57a22ade4ff13a53077620595544`

## Database gate

- Core production schema accepted: 4
- Core target schema: 4
- `migration_required`: `false`
- Minimum current application version: 1.0.10
- Pre-update backup validation: PASS
- Core database dump before and after preparation/health check: identical
- Existing output and recorder profile files: preserved
- `ApplicationUpdateService.prepare_update()`: PASS
- `PostUpdateHealthCheck`: SUCCESS
- Analytics ATT & OT sequential migration through schema 5, including v4 to v5
  backup and employee data preservation: PASS

The ATT & OT analytics database is separate from the OAS-K core database. Its
internal schema 5 does not change the release manifest's core schema 4 range.

## Automated tests

- Full suite: 968 passed, 2 skipped
- Update/startup/metadata release gate after version bump: 73 passed
- Focused template, Tk navigation, and ATT & OT regression: 97 passed
- Python compilation check: PASS
- Frozen archive contains ATT & OT modules and the newly built updater: PASS
- Frozen OAS-K Tk shell opened and closed normally: PASS
- ZIP and frozen archive prohibited-data scan: PASS

The only test warning is the intentional duplicate-ZIP-entry rejection fixture.

## One-million-row capacity benchmark

- Rows: 1,000,001
- Batch insert: 8.369 seconds
- Enrichment: 67.925 seconds
- Dashboard query: 0.003 seconds
- Detail page query (200 rows): 0.021 seconds
- Full streaming pass: 3.413 seconds
- Total benchmark: 92.188 seconds
- SQLite database size: 548.96 MiB
- RSS before rebuild: 43.54 MiB
- RSS after rebuild: 46.60 MiB
- Peak RSS: 51.38 MiB
- SQLite integrity: OK
- Foreign-key violations: 0

The bounded-memory path uses batch import/enrichment, SQLite aggregation,
200-row UI pagination, and streaming workbook export.

## Package contents

The application-only ZIP contains exactly:

- `application/`
- `application/OAS-K.exe`
- `manifest.json`
- `release_notes.txt`
- `checksums.sha256`

No database, MDB, Data Root, log, output, backup, or recorder profile is included.
