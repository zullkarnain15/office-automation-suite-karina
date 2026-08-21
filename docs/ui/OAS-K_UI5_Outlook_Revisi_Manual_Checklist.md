# OAS-K UI5 — Outlook Revisi Manual Checklist

## Safe fixture policy

Use only Fake Registry, a unique temporary/test Data Root, a generated test workbook, a fake mailbox client, and a fake engine. Never point this checklist at a production mailbox, production Registry value, `D:\OAS-K\Data`, or a production database. Keep the fake engine incapable of real outbound delivery.

Source launcher:

```powershell
py tools/ui_test/run_unified_ui.py --test-data-root <unique-temporary-path>
```

Opening the launcher must report that neither the suggested Test Data Root nor database was created. Initialization is outside UI5 acceptance and must not be confirmed for this smoke check.

## Acceptance checklist

- [x] Outlook Revisi page opens inside the Unified UI.
- [x] Merely opening the page does not open Outlook, read a workbook/mailbox, create a database/output/job, write Registry, or bootstrap storage.
- [x] Configuration Browse and `.xlsx` validation work.
- [x] Missing required configuration input is rejected without modifying the workbook.
- [x] Mailbox validation is read-only and resolves exact SMTP `karina.hr.1@oto.co.id` plus `Inbox`.
- [x] Wrong mailbox, missing Inbox, and unavailable Outlook block the run without default-Inbox fallback.
- [x] HO and BRANCH each run as one workflow per job.
- [x] Global and manual period/output resolution work and are audited as actual values.
- [x] Rule, sender, recipient, risk, and multiline-template summaries are displayed.
- [x] PREVIEW/dry-run is the default and validation-only performs no send.
- [x] Live SEND requires checkbox, typed `SEND`, and second confirmation before job creation.
- [x] Progress and bounded log events arrive through the Tk thread while the window remains responsive.
- [x] Active destructive work blocks navigation; navigation and busy state recover after completion/failure.
- [x] Cooperative cancellation produces consistent terminal state and retains partial results when present.
- [x] Success, failure, and cancellation result summaries appear.
- [x] Existing output, attachment, process-log, TXT, report, and summary paths can be exposed as recovery actions.
- [x] Dashboard and History read Outlook Revisi jobs.
- [x] Attendance regression remains green.
- [x] HRIS and Utilities are not connected.
- [x] Legacy Outlook Revisi GUI remains available.
- [x] Schema remains 24 tables and no production database/Registry/mailbox is used.

## Executed evidence

The automated safe-fixture acceptance covers configuration and mailbox validation, zero validation side effects, HO, BRANCH, PREVIEW, fake live SEND confirmations, cancellation with partial artifacts, failure, Dashboard/History visibility, schema count, file references, and zero Registry writes after explicit fake-pointer setup.

The source launcher was also started with a unique temporary suggestion and reported `TestRootCreated=False` and `DatabaseCreated=False`. No destructive mailbox test was performed, by design.

One optional in-process real-Tk page test may skip on this machine because Python 3.14 cannot locate Tcl's `init.tcl`. The isolated Tk fixture acceptance passes and all non-optional behavior is covered headlessly.
