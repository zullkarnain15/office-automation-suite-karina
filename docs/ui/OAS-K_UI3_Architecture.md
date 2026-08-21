# OAS-K UI3 Architecture

Status: COMPLETED
Schema: v1 unchanged (24 tables)
Engine integration: None

## Read-only pages

Dashboard uses `DashboardService` to resolve storage, aggregate job counts by
module/status, read the most recent jobs, latest backup, and last persisted
health status. Missing or invalid databases return typed empty/unavailable
results. The page performs one controlled first-show refresh and supports manual
refresh; neither path creates storage or starts an engine.

History uses `HistoryService` with `HistoryFilters`, a fixed page size of 25,
parameterized `limit`/`offset`, and a matching total count. Filters cover module,
status, inclusive date range, and text. Job detail reads file references and
status events. Open actions go through the guarded UI2 filesystem facade. There
is no edit, delete, rerun, or whole-table load.

System Health uses `SystemHealthService` and typed `HealthCheckResult` values.
Opening the page shows `NOT_CHECKED` or the in-memory cache; only `Run Checks`
starts work. Checks cover database, storage paths, Registry pointer, write
access, recovery, and Attendance/Outlook Revisi/HRIS/Utilities configuration
readiness without importing or executing engines. UI3 deliberately chose
zero-write health checks: `system_health_history` is not written.

## Services and repositories

`AppServices` injects the three UI3 facades alongside the UI2 services. They use
short-lived SQLite `mode=ro` connections. New `JobRepository` methods provide
filtered search/count, module-status aggregation, job files, and status events.
`BackupHistoryRepository.get_latest_backup()` provides the latest backup.
Schema and existing write behavior are unchanged.

Dashboard, History refresh, and Run Checks reuse UI2 `TaskRunner`. Worker code
publishes plain results to its queue; the Tk-thread drain owns callbacks and
widget updates. Each page disables its refresh/run action while busy, ignores a
stale result after disposal, and remains navigable and safely closable.

## Visual system

UI3 retains the light shell and locked colors. Font hierarchy and spacing
constants (`4/8/12/16/24`) live in `ui.constants`. Reusable metric, module,
health, and pagination widgets use consistent cards, borders, typography, and
dynamic text wrapping. Health cards use a vertical viewport at constrained
height. History uses a resizing table and scrollbar.

Sidebar widget icons prefer 22×22 RGBA companions in `assets/icons/png`; `.ico`
remains the window-icon source. `IconManager` loads lazily, caches images, and
falls back to text for missing/corrupt PNG. The explicit development generator
does not overwrite unless `--overwrite` is passed and never runs at import or
runtime.

`enable_dpi_awareness()` is Windows-guarded, called before internally creating
Tk, and falls back safely. Window placement reserves low-height screen space,
while the 1000×640 minimum remains enforced. Visual checks covered isolated Tk
scaling previews at 100% and 125%, plus the workstation's actual 150%/144-DPI
mode.

## Read-only guarantees

Automated tests prove missing databases are not created, health history remains
unchanged, Fake Registry receives no write/delete, operational engines and
Configuration Reader are not imported, and schema remains 24 tables. Manual
launch and explicit health checks created no production storage or Registry
values.

## Technical debt and UI4

- History detail is intentionally simple text presentation.
- Health checks provide configuration readiness, not live engine connectivity.
- Dashboard has compact fixed four-column cards rather than breakpoint-driven
  reflow; dynamic wrapping and the supported minimum size cover UI3.
- Screen-reader semantics and a broader multi-monitor DPI transition audit
  remain.

UI4 should activate one operational module at a time behind explicit engine
adapters, cancellation/recovery contracts, and job-history recording. Preserve
the UI3 read-only facades and do not couple engines directly to widgets.
