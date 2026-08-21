# Att Data Repair Manual QA Checklist

Purpose: source-level Windows manual verification guide for Att Data Repair.
This checklist is a guide only; it has not been executed by Codex.

| No | Test Case | Expected Result | Actual Result | PASS/FAIL | Notes | Tester | Date |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Backup project and active database before testing. | Backup is available before any manual run. | | | | | |
| 2 | Start the application from source. | Application starts without build/EXE packaging. | | | | | |
| 3 | Open Dashboard. | Dashboard loads normally. | | | | | |
| 4 | Open Utilities. | Utilities page opens. | | | | | |
| 5 | Verify landing cards. | Three cards are visible: Comparison Result, Attachment Consolidation, Att Data Repair. | | | | | |
| 6 | Open Att Data Repair. | Workspace opens with label Att Data Repair. | | | | | |
| 7 | Inspect layout at normal and narrow window sizes. | No overlapping controls, clipped labels, or unreadable text. | | | | | |
| 8 | Browse Source Report and choose a valid .xlsx file. | File picker accepts .xlsx and path appears in Source Report. | | | | | |
| 9 | Try a non-.xlsx file. | Run/preflight is blocked with a clear .xlsx message. | | | | | |
| 10 | Try a workbook missing Valid_Records or Invalid_Records. | Preflight reports missing required sheet. | | | | | |
| 11 | Enable global period. | Date fields are readonly and show General Settings period. | | | | | |
| 12 | Disable global period. | Local Period Start and Period End can be edited. | | | | | |
| 13 | Use invalid local period start > end. | Run/preflight is blocked. | | | | | |
| 14 | Enable global output. | Output field is readonly and Browse is disabled. | | | | | |
| 15 | Disable global output. | Local Output Folder and Browse are enabled. | | | | | |
| 16 | Run with Generate TXT only. | TXT is generated, Excel report is not generated, summary explains report skip. | | | | | |
| 17 | Run with Generate Excel Report only. | Excel report is generated, TXT is not generated, summary explains TXT skip. | | | | | |
| 18 | Run with both outputs enabled. | TXT and Excel report are generated. | | | | | |
| 19 | Disable both output options. | Run/preflight is blocked. | | | | | |
| 20 | Run a small valid source. | Job completes successfully, output folder is created. | | | | | |
| 21 | Confirm UI responsiveness during run. | UI remains responsive and progress/log update. | | | | | |
| 22 | Click Stop before engine starts. | Cancellation request is accepted before engine execution. | | | | | |
| 23 | Click Stop while engine is running. | UI waits for safe boundary; note current limitation. | | | | | |
| 24 | Verify SUCCESS result. | Status, summary counts, output, report/log buttons are correct. | | | | | |
| 25 | Verify PARTIAL_SUCCESS result. | UI warns about anomaly and report is available. | | | | | |
| 26 | Verify NO_VALID_RECORDS result. | UI states no valid records and points to Anomaly/report when available. | | | | | |
| 27 | Verify FAILED result with corrupt source. | User-facing error is clear; no traceback is shown. | | | | | |
| 28 | Click Open Output. | Actual job folder opens. | | | | | |
| 29 | Click Open Report. | Excel audit report opens when generated; button disabled otherwise. | | | | | |
| 30 | Click Open Log. | Process.log opens when available. | | | | | |
| 31 | Click Retry. | UI is ready for a new run and does not reuse the old job folder. | | | | | |
| 32 | Open History. | Att Data Repair job appears under Utilities history. | | | | | |
| 33 | Verify configuration import/export. | Att_Data_Repair sheet roundtrips through Settings/import/export. | | | | | |
| 34 | Open Excel report in Excel. | Eight expected sheets are present and readable. | | | | | |
| 35 | Open TXT in Notepad. | TXT naming/content follows Att_Data_Repair_[Workflow]-[NNN]_[RRRR].txt. | | | | | |
| 36 | Compare source workbook hash/size before and after run. | Source workbook is unchanged. | | | | | |
| 37 | Close application normally. | App closes without worker orphan warning. | | | | | |
| 38 | Reopen application and database. | Database remains valid and history can still be viewed. | | | | | |
