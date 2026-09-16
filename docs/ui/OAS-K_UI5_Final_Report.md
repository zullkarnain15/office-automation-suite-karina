# OAS-K Sprint UI5 — Final Report

## Status

**COMPLETED** — all UI5 acceptance criteria are satisfied. Work stops at UI5; UI6 has not been started.

## Delivered integration

The Outlook Revisi page is active in the Unified UI with Configuration, Mailbox, Period, Workflow, Output Location, Processing Options, Validation Summary, Outbound Safety, Progress, Process Log, Result Summary, and Recovery Actions sections.

Its architecture is `Page -> OutlookRevisiService -> OutlookRevisiAdapter -> legacy reader/engine/client`. The page has no direct Outlook COM, SMTP, reader, or engine dependency. Typed models carry requests, validation, mailbox state, outbound safety, events, results, output references, defaults, and cancellation.

The adapter uses the existing `OutlookRevisiEngine(configuration_file, workflow, dry_run, message_limit, client).run()` API. Optional backward-compatible engine progress/cancellation hooks and a read-only mailbox validator were added; Outlook business rules and output writers were not replaced.

## Safety and behavior

- Mailbox selection is locked to exact SMTP `karina.hr.1@oto.co.id` and `Inbox`; display name `RPA.HR01` is informational only.
- There is no default Inbox, first mailbox, current user, or display-name fallback. Missing/wrong mailbox or Inbox blocks the run.
- Configuration validation uses the legacy reader and never modifies the source workbook. Runtime output/payroll overrides exist only in a temporary workbook copy.
- HO and BRANCH remain separate one-workflow jobs.
- Existing database globals and manual per-run output/period overrides are resolved and their actual values/flags are audited. A missing audit database blocks execution but not manual validation and does not bootstrap storage.
- PREVIEW/dry-run is default. Validation-only cannot send. Auto Reply or SEND requires checkbox, typed `SEND`, and a second confirmation before job creation; the typed value is not persisted.
- Work runs in the shared background runner. Tk callbacks are queued through `after`; workers do not touch widgets. Busy/navigation state recovers after success and failure, and active destructive work is guarded.
- Cancellation is cooperative and checked before connection/outbound/finalization and throughout message processing. Late cancellation cannot overwrite a terminal state. Partial files/counts are retained when the engine produced them.
- Audit lifecycle covers PENDING, RUNNING, COMPLETED/COMPLETED_WITH_WARNING, FAILED, PAUSED/CANCEL_REQUESTED, and CANCELLED. Only existing file paths are recorded.
- Recovery actions expose existing output, attachment, configuration, and process-log locations plus retry-as-new-job and Settings navigation. There is no automatic retry or resend.

## Verification results

| Verification | Result |
|---|---:|
| UI5 Outlook Revisi directory | 7 passed, 1 optional Tk skip |
| Entire UI suite | 152 passed |
| Database + storage + recovery + UI | 390 passed, 1 optional Tk skip |
| Entire project | 527 passed |
| Existing Outlook Revisi regressions | 50 passed |
| Attendance regressions | 34 passed |
| Ruff (`ui tests/ui tools/ui_test`) | passed |
| Schema v1 | version 1, 24 required tables |
| Legacy GUI import | passed (`OutlookRevisiGUI`) |
| Database artefact scan | no `.db`, `.sqlite`, or `.sqlite3` in worktree |

The optional skip is environmental: this Python 3.14 installation intermittently cannot locate Tcl `init.tcl` for an in-process real-Tk page fixture. The isolated fake-fixture acceptance passes, and the full UI suite completed with all 152 tests passing in its final run.

## Smoke and manual-safe acceptance

The isolated acceptance uses Fake Registry, a temporary Data Root/database, a generated workbook, fake mailbox client, and fake engine with no real outbound capability. It verified config/mailbox checks, exact target, no validation output/job, HO, BRANCH, PREVIEW, confirmed fake SEND, cancellation/partial artefacts, failure recovery, Dashboard/History, 24-table schema, existing-file references, and zero UI Registry writes after the explicit fake test pointer was established.

The source launcher was run as `py tools/ui_test/run_unified_ui.py --test-data-root <unique-temporary-path>`. It opened without creating the suggested root or database (`TestRootCreated=False`, `DatabaseCreated=False`). No production mailbox, `D:\OAS-K\Data`, production Registry, production database, EXE, build, or dist was used.

Opening the Outlook Revisi page alone therefore performs no workbook read, Outlook/mailbox access, database/output/job creation, Registry write, bootstrap, import/export, backup/restore, database import, or reset.

## Compatibility and boundaries

The legacy GUI remains available. Outlook subject/sender/CC, attachment, template, output naming, and related regressions pass. Attendance remains green. HRIS and Utilities engines are not imported or connected by UI5. `main.py`, schema v1, `shared/config_manager.py`, the legacy workbook/template, and assets were not changed by UI5. Pre-existing dirty changes in `main.py` and assets were preserved rather than reset.

## Files created or changed by UI5

Created:

- `ui/outlook_revisi_models.py`
- `ui/adapters/outlook_revisi_adapter.py`
- `ui/services/outlook_revisi_service.py`
- `tests/ui/adapters/test_outlook_revisi_adapter.py`
- `tests/ui/services/test_outlook_revisi_service.py`
- `tests/ui/outlook_revisi/__init__.py`
- `tests/ui/outlook_revisi/test_outlook_revisi_page.py`
- `tests/ui/outlook_revisi/test_outlook_revisi_fixture_acceptance.py`
- `docs/ui/OAS-K_UI5_Outlook_Revisi_Architecture.md`
- `docs/ui/OAS-K_UI5_Outlook_Revisi_Manual_Checklist.md`
- `docs/ui/OAS-K_UI5_Final_Report.md`

Updated:

- `ui/pages/outlook_revisi_page.py`
- `ui/services/protocols.py`
- `ui/services/service_container.py`
- `ui/services/task_runner.py`
- `tests/ui/test_boundaries.py`
- `tests/ui/services/test_task_and_recovery_services.py`
- `tests/ui/attendance/test_attendance_fixture_acceptance.py` (Tk lifecycle stabilization only)
- `outlook/engine.py` (optional progress/cancellation hooks)
- `outlook/downloader.py` (exact-SMTP mailbox safety and read-only validation)

## Technical debt

- The local Python 3.14 Tcl installation should be repaired so every optional in-process Tk test can run deterministically without subprocess isolation.
- COM behavior still requires a controlled Windows/Outlook staging machine for non-destructive real-client certification; CI intentionally uses fakes.
- Engine progress is coarse because the legacy engine does not expose fine-grained structured events for every internal operation.
- Cancellation cannot safely interrupt a COM/SMTP call already in progress; it stops at the next cooperative checkpoint.
- The engine's single `MM-YYYY` payroll-period contract requires start/end dates to remain within one calendar month.

## UI6 recommendation

For UI6, integrate HRIS through the same typed Page/Service/Adapter boundary, first auditing the real engine and assisted/manual steps. Reuse the TaskRunner, audit lifecycle, side-effect-free page construction, explicit destructive-operation guards, and fake-fixture acceptance. Do not begin that work until UI6 is explicitly authorized.
