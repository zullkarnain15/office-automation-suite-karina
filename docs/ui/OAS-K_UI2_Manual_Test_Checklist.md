# OAS-K UI2 Manual Test Checklist

Use an isolated test location and fake Registry:

```powershell
py tools/ui_test/run_unified_ui.py ^
  --test-data-root "C:\Temp\OAS-K-UI2-Test\Data"
```

The path is only a suggestion until Initialize is explicitly confirmed. Do not
select `D:\OAS-K\Data` for manual UI2 testing.

## Settings shell

- [ ] Settings opens with General, Storage & Database, Import / Export
  Configuration, Backup & Recovery, and HRIS Recorder Profiles.
- [ ] Merely opening Settings creates no folder/database and writes no Registry.
- [ ] Navigation remains responsive while a non-destructive task runs.
- [ ] A destructive task blocks leaving Settings until it completes.

## General

- [ ] Load displays empty values on a new test database.
- [ ] Browse changes the field but does not save.
- [ ] Invalid or partial periods are rejected.
- [ ] Save shows an old/new confirmation and persists only after approval.
- [ ] Reset Unsaved Changes restores the last loaded/saved values.
- [ ] Module usage shows period as unavailable for Attachment Consolidation.

## Storage and database

- [ ] Refresh shows the test Data Root suggestion without creating it.
- [ ] Initialize previews folders and requires confirmation.
- [ ] Registry persistence asks separately and remains fake in test mode.
- [ ] Alternate test path initializes schema v1 successfully.
- [ ] Change Data Location defaults output/log copying off and retains source.
- [ ] Validate Database displays integrity, foreign keys, schema, tables,
  metadata, warnings, and errors.

## Configuration

- [ ] One or multiple workbooks produce a read-only preview.
- [ ] Changes, issues, destructive flags, warnings, errors, and critical issues
  are visible.
- [ ] Global conflict requires explicit output/period values and preview rebuild.
- [ ] Invalid preview cannot commit.
- [ ] Confirmed modules commit atomically.
- [ ] Current Configuration export validates and does not silently overwrite.
- [ ] Save Template Copy As leaves the repository template unchanged.

## Backup and recovery

- [ ] Backup Database reports path, SHA-256, size, and success.
- [ ] Application Data backup includes recorder profiles; output is excluded.
- [ ] Restore candidate details appear before confirmation.
- [ ] Restore result reports pre-operation backup and rollback state.
- [ ] Import Existing Database explains copy/source retention.
- [ ] Reset remains disabled logically until exact `RESET` and second approval.
- [ ] Recovery Status provides recommendations but runs no automatic action.

## Recorder profiles and safety

- [ ] Valid JSON object imports and validates.
- [ ] Invalid/non-JSON, absolute, and traversal references are rejected.
- [ ] Duplicate filename requires confirmation.
- [ ] Remove Reference does not delete the JSON file.
- [ ] UI stays responsive and errors do not close the application.
- [ ] No module engine starts and the legacy Configuration Reader is not called.
- [ ] `main.py`, schema, template, legacy workbooks, assets, build, and dist are
  unchanged.
