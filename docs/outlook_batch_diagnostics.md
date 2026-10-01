# Outlook batch reading and diagnostics

The Outlook engine now snapshots candidate metadata (including EntryID and
StoreID) without retaining live MailItem objects or downloading attachments.
It then opens one selected-workflow candidate at a time, downloads attachments,
processes the email, and releases its MailItem in a finally block. Processing
uses the snapshot IDs so moving emails does not change iteration order.

ReceivedTime descending order, candidate limits, workflow rules and outbound
confirmation remain in effect. A sorting failure is recorded and Outlook's
returned order is used. Other-workflow and already-processed candidates do not
need to be reopened or have their attachments downloaded. Cancellation is
checked during scanning and between candidates.

Before sorting or enumeration, Items.Restrict excludes MessageClass families
IPM.Outlook.Recall and IPM.Recall.Report (including subclasses). This prevents
COM wrapping failures before item.Class can be inspected. The same filter is
used for SMTP BCC recovery. A second MessageClass guard runs before MailItem
properties. No recall item is moved, deleted, downloaded or counted toward the
candidate limit. A subject containing the word Recall is not a reason to skip
an otherwise ordinary email. If the collection filter fails, processing stops
with diagnostics instead of falling back to the unsafe unfiltered collection.
RECALL_ITEMS_EXCLUDED records the count at filtering time; concurrent mailbox
changes can affect this count. RECALL_COUNT_UNAVAILABLE does not disable filtering.

References: [Outlook message classes](https://learn.microsoft.com/en-us/office/vba/outlook/concepts/forms/item-types-and-message-classes),
[Items.Restrict](https://learn.microsoft.com/en-us/office/vba/api/outlook.items.restrict),
and [DASL string comparisons](https://learn.microsoft.com/en-us/office/vba/outlook/how-to/search-and-filter/filtering-items-using-a-string-comparison).

Once configuration and Output Root are resolved and the job directory is
created, Process.log is opened before mailbox access. Diagnostic JSON lines
are flushed during execution; final human-readable report summaries are
appended without deleting the diagnostic trail. An unavailable configuration
or unwritable output location can still prevent creation of this file.

For a failure, use History > View Details > PROCESS_LOG, or Buka Log on the
Outlook result. The adapter exposes the log even when the engine exits early.
Look for FATAL and the preceding operation. MESSAGE_ID / MESSAGE identify the
scanned email; PROCESS_MESSAGE identifies a candidate being processed.
SAVE_ATTACHMENT includes the attachment filename and destination. FATAL
includes the exception, HRESULT when available, and traceback. The log contains
sender addresses, subjects and local paths; it does not record message bodies
or attachment contents.

This change does not add retries, skip failed attendance emails, change database schema,
or implement restart/resume guarantees. Unexpected errors still fail the job,
with the diagnostic trail retained. It addresses object retention and missing
diagnostics; it does not establish the cause of a particular production COM
failure without evidence from the new log.

Tests cover batches of 5, 100, 250 and 500 with on-demand object wrappers,
mailbox mutation, candidate filtering, cancellation, real attachment parsing,
injected read/save failures and failure-log artifact exposure. Real Outlook
and production SMB behavior still require controlled deployment verification.
