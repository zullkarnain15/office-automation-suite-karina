# OAS-K Development Rules

- Do not build, rebuild, package, or export any OAS-K executable unless the
  user explicitly requests an EXE build in the current conversation.
- This prohibition includes running PyInstaller, editing build output for the
  purpose of producing an EXE, or replacing files under `dist/`.
- Code changes, tests, compilation checks, and source-level GUI runs do not
  authorize an EXE build.

## Release Database Gate

- Before creating any OAS-K release package, determine the schema version of
  the production database that the package must accept. Do not assume it is
  already equal to `SCHEMA_VERSION`.
- Set `database_schema_from`, `database_schema_to`, and `migration_required`
  in `manifest.json` deliberately. The declared range must cover the active
  production schema and must match the migrations shipped by the new app.
- A release is not ready until automated tests prove all of these database
  stages: package validation against the old schema, pre-update backup using
  that old schema, sequential migration to the current schema, post-migration
  database validation, and preservation of existing production data.
- Run the update and startup-migration test suites before packaging. For a
  schema-changing release, also run an isolated
  end-to-end smoke test from the oldest supported production schema through
  `ApplicationUpdateService.prepare_update()` and `PostUpdateHealthCheck`.
- Never place a development database, production database, `.db`, `.mdb`,
  Data Root, logs, output, backup, or recorder profiles inside an
  application-only update ZIP.
- Never instruct production users to copy SQL or a development database over
  the active database. Database changes must use versioned migrations and must
  create a verified backup first.
