# OAS-K UI5 — Outlook Revisi Architecture

## Scope

UI5 activates Outlook Revisi inside the existing single-window Unified UI. The integration preserves the legacy configuration reader, engine business rules, output formats, HO/BRANCH separation, and legacy GUI.

The dependency direction is:

`OutlookRevisiPage -> OutlookRevisiService -> OutlookRevisiAdapter -> OutlookRevisiConfigurationReader / OutlookRevisiEngine / OutlookComClient`

The page never imports or calls Outlook COM, SMTP, the configuration reader, or the engine directly.

## Page structure

The page contains Configuration, Mailbox, Period, Workflow, Output Location, Processing Options, Validation Summary, Outbound Safety, Progress, Process Log, Result Summary, and Recovery Actions sections. It uses the UI3 visual system and does not create another `Toplevel` application window.

Construction is side-effect free: it does not read a workbook, open Outlook, read a mailbox, create an output folder/database/job, or send mail. `on_show()` only asks the service for existing database defaults; it never bootstraps a database.

## Typed boundary

`ui/outlook_revisi_models.py` defines request, resolved request, validation, mailbox validation, outbound-safety, progress, log, output-file, result, defaults, and cooperative-cancellation models.

`OutlookRevisiService` owns UI-level validation and resolution, safety evidence, audit lifecycle, output references, and terminal status. `OutlookRevisiAdapter` is the sole Unified UI boundary allowed to import the legacy reader and Outlook package. It owns workbook validation, mailbox readiness checks, engine invocation, COM worker initialization, progress/log translation, cancellation translation, and result normalization.

## Existing API used

The adapter invokes the audited runtime contract:

`OutlookRevisiEngine(configuration_file, workflow, dry_run=True, message_limit=None, client=None).run()`

UI5 exposes only real runtime controls: safe preview/dry-run and an optional message limit. It does not invent independent extraction, TXT, report, summary, validation, or reply switches because those are an integrated engine workflow.

The engine constructor gained optional `progress_callback` and `cancellation_requested` hooks. Existing callers remain valid. `OutlookProcessResult` gained a backward-compatible `cancelled=False` field.

## Configuration and per-run overrides

The legacy `OutlookRevisiConfigurationReader` remains authoritative. Validation requires an `.xlsx` workbook and the reader's General, sender master, subject rule, attachment rule, validation rule, and reply-template inputs. Template newlines are preserved and unknown placeholders become warnings.

The original workbook is never modified. For a run, the adapter creates a temporary copy and changes only the runtime `Output_Root` and `Payroll_Period` values, then removes that copy. Period dates must be ISO dates, ordered, and in one calendar month because the engine consumes a single `MM-YYYY` payroll period.

Global values are read from an existing active SQLite database. Manual validation remains available without a database, but a Unified UI run is blocked and directs the user to Settings. Global/manual output and period choices, plus their resolved values, are recorded on the job.

## Mailbox safety

The locked target is `karina.hr.1@oto.co.id`, display label `RPA.HR01`, folder `Inbox`. Configuration and mailbox validation reject any different SMTP address or folder before a run.

`OutlookComClient.validate_mailbox()` resolves only the configured mailbox and folder; it does not enumerate Inbox messages. Store selection uses exact SMTP identity from MAPI/account delivery-store data. Display-name matching, default Inbox, current-user Inbox, first-mailbox fallback, and silent fallback are not used. The exact shared-recipient resolver remains available when appropriate. Missing Outlook, mailbox, or Inbox is returned as structured validation failure.

## Outbound safety

The Unified UI starts in dry-run/PREVIEW. Validation-only never invokes the engine and cannot send mail.

When configuration enables Auto Reply or `Send_Mode=SEND`, the page displays risk and recipient scope. A live run requires all of the following before a job is created:

1. outbound acknowledgment checkbox;
2. typed `SEND` confirmation;
3. a second final confirmation dialog.

The audit event records that typed confirmation occurred but never stores the typed text itself. Cancellation is checked before outbound work, so a request received before sending prevents the send stage.

## Background execution, progress, and cancellation

The shared `TaskRunner` executes work outside Tk. Workers publish plain model events; widget updates and completion callbacks are drained via Tk's `after` queue. Shutdown cancels the drain callback and rejects late completion delivery. Busy state and navigation are restored on both success and failure.

Progress is coarse and factual rather than a fabricated percentage. The page caps the visible log at 500 lines and provides copy, clear, and open-process-log actions without displaying message bodies.

Cancellation is cooperative at safe checkpoints before connection, after Inbox read, between messages, after processing, before outbound activity, and before summary/finalization. No COM thread is force-terminated. Partial artifacts and counts are normalized when available. The service uses a terminal-state guard so a late cancel cannot overwrite COMPLETED, FAILED, or CANCELLED.

## Audit lifecycle and outputs

The service records `PENDING -> RUNNING -> COMPLETED`, `COMPLETED_WITH_WARNING`, `FAILED`, or `CANCELLED`. Cancellation requests use PAUSED/CANCEL_REQUESTED event semantics compatible with the existing schema. A risky live run records an `OUTBOUND_CONFIRMED` phase before execution.

Only paths that exist are written to `job_files`. Supported normalized roles are OUTPUT_FOLDER, ATTACHMENT_FOLDER, HRIS_TXT, EXCEL_REPORT, PROCESS_LOG, and SUMMARY_JSON. Results retain actual output/period/global flags, workflow, safe mailbox identifier, counts, warnings, error summary, and partial cancellation state. Email bodies and attachment bytes are never stored.

## Recovery and compatibility

Failure/cancellation exposes Open Output Folder, Open Attachment Folder, Open Process Log, Open Configuration Folder, Retry as New Job, and Return to Settings. There is no automatic retry or resend.

The legacy `OutlookRevisiGUI` remains importable. Attendance remains connected as in UI4. HRIS and Utilities engines are not connected by UI5. Schema v1 remains unchanged at 24 tables.
