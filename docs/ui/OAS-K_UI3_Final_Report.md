# OAS-K Sprint UI3 Final Report

Date: 2026-07-21
Status: COMPLETED
Work stopped after UI3.

## Delivered

- Dashboard: database/Data Root/backup/health summary, four module cards, ten
  most-recent activities, manual refresh, empty state, and guarded output open.
- History: module/status/date/text filters, 25-row pagination, total count,
  output/log/report open actions, and job/file/status-event detail.
- System Health: explicit zero-write checks for database, paths, Registry,
  write access, recovery, and four configuration readiness groups.
- Services: `DashboardService`, `HistoryService`, and `SystemHealthService`
  injected through `AppServices` and executed by the UI2 task runner.
- Repository support: parameterized `search_jobs`, `count_search_results`,
  `count_jobs_by_module_status`, `get_job_files`, `get_status_events`, and
  `get_latest_backup`; all are read-only.
- Visual system: centralized typography/spacing, responsive wrapping, metric and
  health cards, pagination, scrollable health viewport, polished sidebar active
  state, and guarded DPI-aware placement.
- Icons: 28 generated 22×22 RGBA PNG companions (including every required
  sidebar/status/action icon) while preserving all source ICO files.

## Verification

| Scope | Result |
|---|---|
| `py -m pytest tests/ui` | 99 passed |
| `py -m pytest tests/database tests/storage tests/recovery tests/ui` | 338 passed |
| `py -m pytest` | 474 passed |
| `py -m ruff check ui tests/ui tools/ui_test tools/assets` | All checks passed |
| Schema | v1, exactly 24 required tables |
| Manual launcher | Responsive; Dashboard/History/System Health inspected |
| DPI visual | 100%, 125% isolated previews; actual 150%/144 DPI |

Fake Registry and temporary Data Root smoke checks observed zero Registry
writes/deletes, zero folder/database creation, and no bootstrap. Dashboard and
History use SQLite read-only mode. System Health stores its cache only in memory
and does not write `system_health_history`.

No Attendance, Outlook Revisi, HRIS, or Utilities engine is imported or
connected. Configuration Reader, schema v1, `main.py`, legacy workbooks, unified
template, format output, build, `dist`, and PyInstaller configuration were not
changed by UI3. No EXE or production database was created.

## New files

- `assets/icons/png/*.png`
- `tools/assets/generate_png_companions.py`
- `ui/dpi.py`
- `ui/services/dashboard_service.py`
- `ui/services/history_service.py`
- `ui/services/system_health_service.py`
- `ui/widgets/metric_card.py`
- `ui/widgets/health_status_card.py`
- `ui/widgets/pagination_bar.py`
- `tests/ui/dashboard/*`
- `tests/ui/history/*`
- `tests/ui/system_health/*`
- `tests/ui/visual/*`
- `docs/ui/OAS-K_UI3_Architecture.md`
- `docs/ui/OAS-K_UI3_Visual_Manual_Checklist.md`
- `docs/ui/OAS-K_UI3_Final_Report.md`

## Updated files

- `shared/database/repositories/job_repository.py`
- `shared/database/repositories/backup_history_repository.py`
- `ui/app.py`, `ui/constants.py`, `ui/icon_manager.py`, `ui/style_manager.py`
- `ui/pages/base_page.py`, `ui/pages/dashboard_page.py`,
  `ui/pages/history_page.py`, `ui/pages/system_health_page.py`
- `ui/services/service_container.py`
- `ui/widgets/__init__.py`, `ui/widgets/header.py`, `ui/widgets/sidebar.py`

Existing UI files were mechanically normalized by Ruff formatting; no business
rule or engine behavior changed.

## Technical debt and UI4 recommendation

History detail presentation, accessibility semantics, multi-monitor DPI
transitions, and richer health recommendations can be improved. Readiness is
configuration-only by design, and health history persistence remains disabled.

UI4 should connect at most one approved engine through an adapter/service—not
directly from widgets—with explicit start/cancel/recovery behavior and normalized
job-history writes. UI3 itself introduces no engine integration.
