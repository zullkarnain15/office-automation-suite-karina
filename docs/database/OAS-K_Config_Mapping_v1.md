# OAS-K Configuration Mapping v1

Status: Sprint DB0 mapping proposal
Source workbooks modified: No
Database created: No

## 1. Mapping rules

- `Current Data Type` describes the actual workbook cell type, not only the
  intended type.
- `Required` is based on the current reader/consumer. An active table row may
  have stricter requirements than an inactive template row.
- `— / not imported` means the value is documentation, duplicate, unused by
  current runtime code, or unsafe to activate without a separate decision.
- Boolean text (`Y/N`, `TRUE/FALSE`) is normalized to INTEGER `1/0`.
- Workflow text (`HO`, `Branch`, `All`) is normalized to controlled uppercase.
- Dates and timestamps are converted to ISO only after preview validation.
- Every import preserves the source workbook hash and rejected-row diagnostics.

## 2. Attendance workbook

Workbook: `config/attendance/OAS-K_Attendance_Configuration.xlsx`

Actual sheets: `General`, `MDB_Branch`, `MDB_HO`, `Output`, `Reference`.
The reader requires the first four. `Reference` is present but not read.

### General

| Workbook | Sheet | Excel Column or Parameter | Current Data Type | Required | Current Consumer | Proposed SQLite Table | Proposed SQLite Column | Proposed SQLite Type | Primary/Unique Rule | Default Value | Validation Rule | Migration Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Attendance | General | `Split_TXT_Rows` | INTEGER | No | Attendance engine | `attendance_settings` | `split_txt_rows` | INTEGER | Singleton | `10000` | `> 0` | Import directly |
| Attendance | General | `Generate_Report` | TEXT boolean | No | Not consumed; GUI supplies run flag | `attendance_settings` | `generate_report_default` | INTEGER | Singleton | `1` | `0/1` | Treat as future GUI default, not an engine rule |
| Attendance | General | `Date_Format` | TEXT | No | Not consumed; fixed app constant | — | — | — | — | `MM/DD/YYYY` | Exact legacy value if exported | Do not activate in DB1 |
| Attendance | General | `Time_Format` | TEXT | No | Not consumed; fixed app constant | — | — | — | — | `HH:MM` | Exact legacy value if exported | Do not activate in DB1 |
| Attendance | General | `Default_Workflow` | TEXT | No | Not consumed by engine | `attendance_settings` | `default_workflow` | TEXT | Singleton | `HO` | `HO/BRANCH` | UI preference only |
| Attendance | General | `OutputFolder` | TEXT absolute path | Yes when config output selected | Reader and Attendance GUI | `global_settings` | `output_root` | TEXT | Singleton | Data-root output | Absolute local writable path | Becomes global candidate; preview required |
| Attendance | General | `Payroll_Periode_From` at row 8 | Excel DATE | Yes when config dates selected | Attendance GUI reads `B8` by position | `global_settings` | `period_start` | TEXT | Singleton | NULL | ISO date | Key spelling retained only in legacy export |
| Attendance | General | duplicate `Payroll_Periode_From` at row 9 | Excel DATE | Yes when config dates selected | Attendance GUI reads `B9` by position | `global_settings` | `period_end` | TEXT | Singleton | NULL | ISO date and `>= period_start` | Typo; logically `Payroll_Periode_To`; importer must use row position/header repair, not reader dictionary |

Important contract issue: `AttendanceConfigurationReader` returns only seven
General keys because the duplicate row-9 key overwrites row 8. The GUI avoids
this accidentally by reading `B8:B9` directly. DB1 must have a dedicated
Attendance importer that reports and repairs this duplicate in preview.

### MDB_HO and MDB_Branch

| Workbook | Sheet | Excel Column or Parameter | Current Data Type | Required | Current Consumer | Proposed SQLite Table | Proposed SQLite Column | Proposed SQLite Type | Primary/Unique Rule | Default Value | Validation Rule | Migration Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Attendance | MDB_HO / MDB_Branch | `Active` | TEXT `Y/N` | Yes | Reader filters active rows | `attendance_sources` | `is_active` | INTEGER | With source row | `0` | `0/1` | Preserve inactive rows for round-trip |
| Attendance | MDB_HO | `Company` | TEXT | Required for active row | Engine uses as code/summary | `attendance_sources` | `source_code` | TEXT | `UNIQUE(workflow, source_code)` | — | Non-empty trimmed | Set workflow `HO` |
| Attendance | MDB_HO | `Description` | TEXT | No | Report/log display | `attendance_sources` | `source_name` | TEXT | — | Empty | Trimmed | Preserve |
| Attendance | MDB_HO | `MDB_Path` | TEXT path | Required for active row | Extractor | `attendance_sources` | `mdb_path` | TEXT | — | NULL | Existing `.mdb` file at run time | Import may accept missing path only for inactive row |
| Attendance | MDB_Branch | `Branch_Code` | TEXT | Required for active row | Engine uses as code/summary | `attendance_sources` | `source_code` | TEXT | `UNIQUE(workflow, source_code)` | — | Non-empty trimmed | Set workflow `BRANCH` |
| Attendance | MDB_Branch | `Branch_Name` | TEXT | No | Report/log display | `attendance_sources` | `source_name` | TEXT | — | Empty | Trimmed | Preserve |
| Attendance | MDB_Branch | `MDB_Path` | TEXT path | Required for active row | Extractor | `attendance_sources` | `mdb_path` | TEXT | — | NULL | Existing `.mdb` file at run time | Same rule as HO |

### Output and Reference

| Workbook | Sheet | Excel Column or Parameter | Current Data Type | Required | Current Consumer | Proposed SQLite Table | Proposed SQLite Column | Proposed SQLite Type | Primary/Unique Rule | Default Value | Validation Rule | Migration Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Attendance | Output | `Output_Root` | TEXT relative path | Fallback only | Reader fallback after `General.OutputFolder` | `global_settings` | `output_root` | TEXT | Singleton | Data-root output | Resolve and compare with General path | Reject conflicting resolved roots; General currently wins |
| Attendance | Output | `HO_TXT_Relative_Path` | TEXT | No | Not consumed | — | — | — | — | `HO\TXT` | Preserve in legacy export | Output naming remains engine-owned |
| Attendance | Output | `HO_Report_Relative_Path` | TEXT | No | Not consumed | — | — | — | — | `HO\Report` | Preserve in legacy export | Not active DB config |
| Attendance | Output | `Branch_TXT_Relative_Path` | TEXT | No | Not consumed | — | — | — | — | `Branch\TXT` | Preserve in legacy export | Not active DB config |
| Attendance | Output | `Branch_Report_Relative_Path` | TEXT | No | Not consumed | — | — | — | — | `Branch\Report` | Preserve in legacy export | Not active DB config |
| Attendance | Output | `Job_Folder_Format` | TEXT | No | Not consumed; engine hardcodes timestamp | — | — | — | — | `YYYYMMDD_HHMMSS` | Preserve in legacy export | Do not imply runtime configurability |
| Attendance | Reference | `Item`, `Rule` rows | TEXT | No | Not read | — | — | — | — | Workbook guide | Non-empty documentation | Keep in templates/legacy export; do not create relational config |

## 3. HRIS workbook

Active workbook: `config/hris/OAS-K_HRIS_Configuration.xlsx`.

`OAS-K_HRIS_Configuration.pre_assisted_backup.xlsx` is a backup, not an
independent active configuration. It lacks `Assisted_Steps` and the 20 assisted/
verification settings appended to `Upload`. DB1 must never import active and
backup files as two modules.

Actual active sheets: `General`, `Run_Control`, `Browser`, `Upload`,
`Reference`, `Assisted_Steps`.

### General

| Workbook | Sheet | Excel Column or Parameter | Current Data Type | Required | Current Consumer | Proposed SQLite Table | Proposed SQLite Column | Proposed SQLite Type | Primary/Unique Rule | Default Value | Validation Rule | Migration Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HRIS | General | `HRIS_URL` | TEXT URL | Yes | HRIS browser | `hris_settings` | `hris_url` | TEXT | Singleton | — | Non-empty URL; no embedded credentials | Current value is mock and must not auto-activate |
| HRIS | General | `Default_Workflow` | TEXT | No | Not consumed | — | — | — | — | `HO` | Preserve for legacy export | Unified UI preference can be designed later |
| HRIS | General | `Default_Browser` | TEXT | No | Not consumed | — | — | — | — | `Edge` | Preserve for legacy export | `Browser_Channel` is authoritative runtime key |
| HRIS | General | `Retry_Count` | INTEGER | No | Not consumed | — | — | — | — | `1` | Non-negative | Do not activate without approved retry semantics |
| HRIS | General | `Timeout_Seconds` | INTEGER | No | Not consumed; browser has hardcoded waits | — | — | — | — | `30` | Positive | Preserve only |
| HRIS | General | `Start_Mode` | TEXT | No | Not consumed | — | — | — | — | `New` | `New/Resume` | Current resume behavior is summary-driven, not this key |
| HRIS | General | `Folder_Upload_Path` | TEXT path | Yes in GUI | Reader output resolver | `global_settings` | `output_root` | TEXT | Singleton | Data-root output | Local writable path | If path ends in `HRIS`, preview parent as global output candidate |

### Run_Control

| Workbook | Sheet | Excel Column or Parameter | Current Data Type | Required | Current Consumer | Proposed SQLite Table | Proposed SQLite Column | Proposed SQLite Type | Primary/Unique Rule | Default Value | Validation Rule | Migration Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HRIS | Run_Control | `Active` | TEXT `Y/N` | Yes | Reader | `hris_run_controls` | `is_active` | INTEGER | — | `0` | `0/1` | Preserve inactive rows |
| HRIS | Run_Control | `Sequence` | INTEGER | Active row | Job manager | `hris_run_controls` | `sequence` | INTEGER | `UNIQUE(workflow, sequence)` | — | `> 0` | No gaps required, but duplicates reject |
| HRIS | Run_Control | `Workflow` | TEXT | Active row | Reader/job manager | `hris_run_controls` | `workflow` | TEXT | With sequence/ID | — | `HO/BRANCH` | Normalize `Branch` to `BRANCH` |
| HRIS | Run_Control | `Run_Control_ID` | TEXT | Active row | Upload plan | `hris_run_controls` | `run_control_id` | TEXT | `UNIQUE(workflow, run_control_id)` | — | Non-empty | Preserve `001`, `02`, and other leading zeros exactly |
| HRIS | Run_Control | `Description` | TEXT | No | Upload plan/report | `hris_run_controls` | `description` | TEXT | — | Empty | Trimmed | Preserve |

### Browser

| Workbook | Sheet | Excel Column or Parameter | Current Data Type | Required | Current Consumer | Proposed SQLite Table | Proposed SQLite Column | Proposed SQLite Type | Primary/Unique Rule | Default Value | Validation Rule | Migration Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HRIS | Browser | `Browser` | TEXT | No | Not consumed | — | — | — | — | `Edge` | Preserve | Duplicate concept; do not import |
| HRIS | Browser | `Headless` | TEXT boolean | No | HRIS browser | `hris_settings` | `browser_headless` | INTEGER | Singleton | `0` | `0/1` | Import |
| HRIS | Browser | `Use_Profile` | TEXT boolean | No | Not consumed | — | — | — | — | `TRUE` | Preserve | Click profile has separate active path/validation |
| HRIS | Browser | `Browser_Channel` | TEXT | No | HRIS browser | `hris_settings` | `browser_channel` | TEXT | Singleton | `msedge` | Allow-listed browser channel | Current Edge contract |
| HRIS | Browser | `Close_Browser_After_Finish` | TEXT boolean | No | Not consumed | — | — | — | — | `FALSE` | Preserve | Do not expose inactive switch |

The workbook validation on `B3:B6` mixes `TRUE`, `FALSE`, and `msedge` for four
different parameters. DB1 validation must use parameter-specific rules rather
than reproduce this range.

### Upload

| Workbook | Sheet | Excel Column or Parameter | Current Data Type | Required | Current Consumer | Proposed SQLite Table | Proposed SQLite Column | Proposed SQLite Type | Primary/Unique Rule | Default Value | Validation Rule | Migration Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HRIS | Upload | `Move_Success_To_Uploaded` | TEXT boolean | No | Not consumed; movement is current behavior | — | — | — | — | `TRUE` | Preserve | Do not create a false runtime switch |
| HRIS | Upload | `Move_Failed_To_Failed` | TEXT boolean | No | Not consumed | — | — | — | — | `TRUE` | Preserve | Same |
| HRIS | Upload | `Generate_Upload_Report` | TEXT boolean | No | Not consumed | — | — | — | — | `TRUE` | Preserve | Report generation remains stable |
| HRIS | Upload | `Generate_Process_Log` | TEXT boolean | No | Not consumed | — | — | — | — | `TRUE` | Preserve | Log remains required evidence |
| HRIS | Upload | `Generate_Summary_JSON` | TEXT boolean | No | Not consumed | — | — | — | — | `TRUE` | Preserve | Summary remains required evidence |
| HRIS | Upload | `Stop_On_First_Failure` | TEXT boolean | No | HRIS engine | `hris_settings` | `stop_on_first_failure` | INTEGER | Singleton | `1` | `0/1` | Import |
| HRIS | Upload | `Resume_Enabled` | TEXT boolean | No | Not consumed | — | — | — | — | `TRUE` | Preserve | Resume behavior exists but is not gated by this key |
| HRIS | Upload | `Uploaded_Folder_Name` | TEXT | No | Not consumed; writer hardcodes | — | — | — | — | `Upload` | Preserve | Output naming unchanged |
| HRIS | Upload | `Failed_Folder_Name` | TEXT | No | Not consumed; writer hardcodes | — | — | — | — | `Failed` | Preserve | Output naming unchanged |
| HRIS | Upload | `Report_Folder_Name` | TEXT | No | Not consumed; writer hardcodes | — | — | — | — | `Report` | Preserve | Output naming unchanged |
| HRIS | Upload | `Click_Profile_Path` | TEXT path | No | Calibrator/profile loader | `hris_settings` | `click_profile_path` | TEXT | Singleton | Legacy relative path | Existing JSON file when required | Store path only; never profile secrets |
| HRIS | Upload | `Assisted_Mode_Enabled` | TEXT boolean | No | Not consumed | — | — | — | — | `TRUE` | Preserve | Assisted workflow is currently selected by code path |
| HRIS | Upload | `Manual_Recovery_Enabled` | TEXT boolean | No | Assisted replay | `hris_settings` | `manual_recovery_enabled` | INTEGER | Singleton | `1` | `0/1` | Import |
| HRIS | Upload | `Require_Profile_Match` | TEXT boolean | No | HRIS engine | `hris_settings` | `require_profile_match` | INTEGER | Singleton | `1` | `0/1` | Import |
| HRIS | Upload | `Use_Date_From_Config` | TEXT boolean | No | HRIS GUI | `hris_settings` | `use_global_period` | INTEGER | Singleton | `1` for new design | `0/1` | Legacy false means per-run override; do not update global dates |
| HRIS | Upload | `Start_Date` | TEXT date | Conditional | HRIS GUI | `global_settings` | `period_start` | TEXT | Singleton | NULL | Parse `MM/DD/YYYY`, preview ISO | Current value is development data; confirmation required |
| HRIS | Upload | `End_Date` | TEXT date | Conditional | HRIS GUI | `global_settings` | `period_end` | TEXT | Singleton | NULL | Parse and `>= start` | Same |
| HRIS | Upload | `Browser_X` | INTEGER | No | Browser/calibrator | `hris_settings` | `browser_x` | INTEGER | Singleton | `0` | Integer | Import |
| HRIS | Upload | `Browser_Y` | INTEGER | No | Browser/calibrator | `hris_settings` | `browser_y` | INTEGER | Singleton | `0` | Integer | Import |
| HRIS | Upload | `Browser_Width` | INTEGER | No | Browser/calibrator | `hris_settings` | `browser_width` | INTEGER | Singleton | `1200` | `>= 640` | Import |
| HRIS | Upload | `Browser_Height` | INTEGER | No | Browser/calibrator | `hris_settings` | `browser_height` | INTEGER | Singleton | `800` | `>= 480` | Import |
| HRIS | Upload | `Browser_Zoom` | INTEGER | No | Browser/calibrator/profile | `hris_settings` | `browser_zoom` | INTEGER | Singleton | `100` | Positive supported step | Import |
| HRIS | Upload | `Assisted_Verification_Enabled` | TEXT boolean | No | Assisted verifier | `hris_settings` | `verification_enabled` | INTEGER | Singleton | `1` | `0/1` | Import |
| HRIS | Upload | `Verification_Wait_Seconds` | INTEGER | No | Assisted verifier | `hris_settings` | `verification_wait_seconds` | REAL | Singleton | `1` | `>= 0` | Import |
| HRIS | Upload | `Verification_Timeout_Seconds` | INTEGER | No | Assisted verifier | `hris_settings` | `verification_timeout_seconds` | REAL | Singleton | `10` | `>= wait` | Import |
| HRIS | Upload | `Verification_Poll_Seconds` | INTEGER | No | Assisted verifier | `hris_settings` | `verification_poll_seconds` | REAL | Singleton | `1` | `> 0` | Import |
| HRIS | Upload | `Verification_Success_Texts` | TEXT pipe list | No | Assisted verifier | `hris_settings` | `verification_success_texts` | TEXT | Singleton | Current phrases | Non-empty controlled separator | Preserve exact phrase list |
| HRIS | Upload | `Verification_Failure_Texts` | TEXT pipe list | No | Assisted verifier | `hris_settings` | `verification_failure_texts` | TEXT | Singleton | Current phrases | Non-empty controlled separator | Preserve exact phrase list |
| HRIS | Upload | `Manual_Verification_On_Unknown` | TEXT boolean | No | Assisted verifier | `hris_settings` | `manual_verification_on_unknown` | INTEGER | Singleton | `1` | `0/1` | Import |
| HRIS | Upload | `Manual_Verification_On_Error` | TEXT boolean | No | Assisted verifier | `hris_settings` | `manual_verification_on_error` | INTEGER | Singleton | `1` | `0/1` | Import |

### Assisted_Steps and Reference

| Workbook | Sheet | Excel Column or Parameter | Current Data Type | Required | Current Consumer | Proposed SQLite Table | Proposed SQLite Column | Proposed SQLite Type | Primary/Unique Rule | Default Value | Validation Rule | Migration Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HRIS | Assisted_Steps | `Active` | TEXT `Y/N` | Yes | Reader | `hris_assisted_steps` | `is_active` | INTEGER | — | `0` | `0/1` | Preserve inactive steps |
| HRIS | Assisted_Steps | `Sequence` | INTEGER | Active row | Replay ordering | `hris_assisted_steps` | `sequence` | INTEGER | UNIQUE | — | `> 0` | Reject duplicate sequence |
| HRIS | Assisted_Steps | `Step_Name` | TEXT | Active row | Replay/macro resolver | `hris_assisted_steps` | `step_name` | TEXT | UNIQUE | — | Non-empty | Preserve exact canonical names |
| HRIS | Assisted_Steps | `Action` | TEXT | Active row | Reader validation/replay | `hris_assisted_steps` | `action` | TEXT | — | — | Current action allow-list | Import |
| HRIS | Assisted_Steps | `Input_Source` | TEXT | Active row | Reader validation/replay | `hris_assisted_steps` | `input_source` | TEXT | — | `NONE` | Current source allow-list | Import |
| HRIS | Assisted_Steps | `Method` | TEXT | Active row | Reader validation/replay | `hris_assisted_steps` | `method` | TEXT | — | `manual` | Current method allow-list | Import |
| HRIS | Assisted_Steps | `Required` | Excel BOOLEAN | Active row | Replay | `hris_assisted_steps` | `is_required` | INTEGER | — | `0` | `0/1` | Import |
| HRIS | Assisted_Steps | `Wait_After_Seconds` | INTEGER | No | Replay | `hris_assisted_steps` | `wait_after_seconds` | REAL | — | `0` | `>= 0` | Import |
| HRIS | Assisted_Steps | `Description` | TEXT | No | Operator/reference | `hris_assisted_steps` | `description` | TEXT | — | Empty | Trimmed | Preserve |
| HRIS | Reference | `Item`, `Rule` rows | TEXT | Sheet required, rows not read | Legacy reader only checks sheet exists | — | — | — | — | Workbook guide | Non-empty documentation | Keep in template/legacy export; no DB table |

## 4. Outlook Revisi workbook

Active canonical filename:
`config/outlook/OAS-K_Outlook-Revisi_Configuration.xlsx`.

`OAS-K_Outlook-Revisi_Configuration1.xlsx` is byte-for-byte identical
(same SHA-256). It is a duplicate, not another configuration version. Import
preview should choose the canonical filename and report the duplicate.

Actual sheets: `General`, `HO_Sender_Master`, `Branch_Sender_Master`,
`Subject_Rules`, `Attachment_Rules`, `Validation_Rules`, `Reply_Templates`.

### General

| Workbook | Sheet | Excel Column or Parameter | Current Data Type | Required | Current Consumer | Proposed SQLite Table | Proposed SQLite Column | Proposed SQLite Type | Primary/Unique Rule | Default Value | Validation Rule | Migration Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Outlook | General | `Integration_Method` | TEXT | No | Reader/test only; COM client is fixed | `outlook_settings` | `integration_method` | TEXT | Singleton | `OOM_COM` | `OOM_COM` in v1 | Store for explicit compatibility |
| Outlook | General | `Mailbox_SMTP` | TEXT email | Yes | Outlook client/GUI/report | `outlook_settings` | `mailbox_smtp` | TEXT | Singleton | — | Valid mailbox address | Exact address requires operator confirmation |
| Outlook | General | `Source_Folder` | TEXT | No | Outlook client/report | `outlook_settings` | `source_folder` | TEXT | Singleton | `Inbox` | Non-empty folder name | Import |
| Outlook | General | `Reply_From_SMTP` | TEXT email | Conditional | Outlook client | `outlook_settings` | `reply_from_smtp` | TEXT | Singleton | Mailbox address | Valid email | Import |
| Outlook | General | `Send_Transport` | TEXT | No | Outlook client | `outlook_settings` | `send_transport` | TEXT | Singleton | `OUTLOOK` | `OUTLOOK/SMTP` | SMTP requires server/from |
| Outlook | General | `SMTP_Server` | TEXT host | Conditional | Outlook client | `outlook_settings` | `smtp_server` | TEXT | Singleton | Empty | Required for SMTP | No password stored |
| Outlook | General | `SMTP_Port` | INTEGER | Conditional | Outlook client | `outlook_settings` | `smtp_port` | INTEGER | Singleton | `25` | `1..65535` | Import |
| Outlook | General | `SMTP_Timeout_Seconds` | INTEGER | No | Outlook client | `outlook_settings` | `smtp_timeout_seconds` | INTEGER | Singleton | `30` | `> 0` | Import |
| Outlook | General | `Processed_Folder` | TEXT | No | Outlook engine | `outlook_settings` | `processed_folder` | TEXT | Singleton | `Deleted Items` | Non-empty | Current value `Deleted` must be previewed |
| Outlook | General | `Output_Root` | TEXT path | Yes | Reader/engine/GUI | `global_settings` | `output_root` | TEXT | Singleton | Data-root output | Local writable path | Strip module suffix only when preview confirms |
| Outlook | General | `Payroll_Period` | TEXT `MM-YYYY` | Yes for rules/templates | Engine/GUI/report | `global_settings` | `period_start`, `period_end` | TEXT | Singleton | NULL | Valid month; derive full-month dates only with confirmation | Adapter regenerates legacy label |
| Outlook | General | `Resubmit_Deadline` | TEXT localized timestamp | No | Reply template values | `outlook_settings` | `resubmit_deadline` | TEXT | Singleton | NULL | Parse to ISO with timezone | Preserve original text in diagnostic on parse failure |
| Outlook | General | `Auto_Reply_Enabled` | TEXT boolean | No | Engine | `outlook_settings` | `auto_reply_enabled` | INTEGER | Singleton | `0` for safe initial setup | `0/1` | Preview current TRUE prominently |
| Outlook | General | `Send_Mode` | TEXT | No | Engine/client | `outlook_settings` | `send_mode` | TEXT | Singleton | `DRAFT` for safe initial setup | `SEND/DRAFT`; SMTP+DRAFT invalid | Preview current SEND prominently |
| Outlook | General | `PIC_HR_Emails` | Blank/semicolon TEXT | No | Summary recipients | `outlook_summary_recipients` | TO rows | TEXT | Unique type/email | Empty | Valid emails | Split semicolon list |
| Outlook | General | `SPV_PIC_HR_Emails` | Blank/semicolon TEXT | No | Summary CC | `outlook_summary_recipients` | CC rows | TEXT | Unique type/email | Empty | Valid emails | Split semicolon list |
| Outlook | General | `TXT_Max_Lines` | INTEGER | No | Outlook and Attachment Consolidation | `outlook_settings`; `attachment_consolidation_settings` | `txt_max_lines` | INTEGER | Singleton each | `10000` | `> 0` | Copy to both at initial migration, then independent |
| Outlook | General | `Module_Display_Name` | TEXT | No | Report writer | `outlook_settings` | `module_display_name` | TEXT | Singleton | `Outlook Revisi` | Non-empty | Import |
| Outlook | General | `Window_Title` | TEXT | No | Not consumed; GUI hardcodes title | — | — | — | — | Current text | Preserve | Do not activate |
| Outlook | General | missing `Save_SMTP_Copy_To_Sent` | Absent | No | Engine defaults TRUE | `outlook_settings` | `save_smtp_copy_to_sent` | INTEGER | Singleton | `1` | `0/1` | Export Current should include this explicit default |

Workbook validation defects:

- `B13:B14` is constrained to `TRUE/FALSE`, but those cells contain
  `Processed_Folder` and `Output_Root`.
- `B14` also has a conflicting `SEND/DRAFT` validation.
- The intended boolean and send-mode cells are `B17` and `B18`.

DB1 validates by parameter name and must not copy these cell-range mistakes.

### Sender masters

| Workbook | Sheet | Excel Column or Parameter | Current Data Type | Required | Current Consumer | Proposed SQLite Table | Proposed SQLite Column | Proposed SQLite Type | Primary/Unique Rule | Default Value | Validation Rule | Migration Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Outlook | HO/Branch Sender | `Active` | TEXT `Y/N` | Yes | Reader | `outlook_sender_master` | `is_active` | INTEGER | — | `0` | `0/1` | Active blank rows are rejected, not silently accepted |
| Outlook | HO Sender | `Nik_Sender` | TEXT identifier | No | Current reader ignores | `outlook_sender_master` | `sender_nik` | TEXT | — | Empty | Preserve leading zeros | Lossless round-trip |
| Outlook | HO/Branch Sender | `Sender_Name` | TEXT | No | Reader/engine template | `outlook_sender_master` | `sender_name` | TEXT | — | Empty | Trimmed | Import |
| Outlook | HO/Branch Sender | `Sender_Email` | TEXT email | Active row | Reader/matching | `outlook_sender_master` | `sender_email` | TEXT | Composite unique | — | Valid email | Case-insensitive matching |
| Outlook | HO/Branch Sender | `Nik_Spv` | TEXT identifier | No | Current reader ignores | `outlook_sender_master` | `supervisor_nik` | TEXT | — | Empty | Preserve leading zeros | Lossless round-trip |
| Outlook | HO/Branch Sender | `Name_SPV` | TEXT | No | Current reader ignores | `outlook_sender_master` | `supervisor_name` | TEXT | — | Empty | Trimmed | Lossless round-trip |
| Outlook | HO/Branch Sender | `Required_CC_Email` | TEXT email | Business-required for current validation | Reader/engine | `outlook_sender_master` | `required_cc_email` | TEXT | — | Empty | Valid email when rule requires CC | Import |
| Outlook | Branch Sender | `Company` | TEXT | Active Branch row | Reader/subject matching | `outlook_sender_master` | `company_code` | TEXT | Composite unique | — | Non-empty | HO stores empty string |
| Outlook | Branch Sender | `Branch_Code` | TEXT | Active Branch row | Reader/subject matching | `outlook_sender_master` | `branch_code` | TEXT | Composite unique | — | Non-empty | Normalize only whitespace/case for matching |

The HO sheet validation incorrectly applies `Y/N` to `A5:B50` and only `E5`;
only column A should be the active flag. Branch validation on `A5:A250` is
structurally correct.

### Rules and templates

| Workbook | Sheet | Excel Column or Parameter | Current Data Type | Required | Current Consumer | Proposed SQLite Table | Proposed SQLite Column | Proposed SQLite Type | Primary/Unique Rule | Default Value | Validation Rule | Migration Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Outlook | Subject_Rules | `Active` | TEXT `Y/N` | Yes | Reader | `outlook_subject_rules` | `is_active` | INTEGER | — | `0` | `0/1` | Import |
| Outlook | Subject_Rules | `Workflow` | TEXT | Active row | Engine | `outlook_subject_rules` | `workflow` | TEXT | With pattern | — | `HO/BRANCH` | Normalize |
| Outlook | Subject_Rules | `Subject_Pattern` | TEXT template | Active row | Engine | `outlook_subject_rules` | `subject_pattern` | TEXT | `UNIQUE(workflow, pattern)` | — | Supported placeholders only | Preserve braces/text |
| Outlook | Attachment_Rules | `Active` | TEXT `Y/N` | Yes | Reader | `outlook_attachment_rules` | `is_active` | INTEGER | — | `0` | `0/1` | Import |
| Outlook | Attachment_Rules | `Workflow` | TEXT | Active row | Engine | `outlook_attachment_rules` | `workflow` | TEXT | With extension | — | `HO/BRANCH` | Normalize |
| Outlook | Attachment_Rules | `Allowed_Extensions` | Semicolon TEXT | Active row | Reader/engine | `outlook_attachment_rules` | one `extension` row each | TEXT | `UNIQUE(workflow, extension)` | — | Lowercase, begins `.` | Split list transactionally |
| Outlook | Validation_Rules | `Active` | TEXT `Y/N` | Yes | Reader | `outlook_validation_rules` | `is_active` | INTEGER | — | `0` | `0/1` | Import |
| Outlook | Validation_Rules | `Rule_Code` | TEXT | Active row | Engine/parser | `outlook_validation_rules` | `rule_code` | TEXT | `UNIQUE(rule_code, workflow)` | — | Allow-listed code | Preserve exact value semantics |
| Outlook | Validation_Rules | `Workflow` | TEXT | Active row | Reader/engine | `outlook_validation_rules` | `workflow` | TEXT | With code | — | `HO/BRANCH/ALL` | Normalize |
| Outlook | Validation_Rules | `Rule_Value` | TEXT | Depends on code | Engine/parser | `outlook_validation_rules` | `rule_value` | TEXT | — | — | Rule-code-specific validation | Do not coerce every value to one type |
| Outlook | Reply_Templates | `Active` | TEXT `Y/N` | Yes | Reader | `outlook_reply_templates` | `is_active` | INTEGER | — | `0` | `0/1` | Import |
| Outlook | Reply_Templates | `Reply_Code` | TEXT | Active row | Engine lookup | `outlook_reply_templates` | `reply_code` | TEXT | UNIQUE | — | Non-empty uppercase | Import |
| Outlook | Reply_Templates | `Recipient_Type` | TEXT | Active row | Engine | `outlook_reply_templates` | `recipient_type` | TEXT | — | — | `SENDER/PIC_HR` | Import |
| Outlook | Reply_Templates | `Trigger` | TEXT | Active row | Engine lookup | `outlook_reply_templates` | `trigger_code` | TEXT | — | — | Supported trigger | Import |
| Outlook | Reply_Templates | `Subject_Template` | TEXT template | Active row | Engine | `outlook_reply_templates` | `subject_template` | TEXT | — | Empty allowed only if current trigger permits | Placeholder validation | Preserve exactly |
| Outlook | Reply_Templates | `Body_Template` | Multiline TEXT | Active row | Engine | `outlook_reply_templates` | `body_template` | TEXT | — | — | Placeholder validation; non-empty | Preserve line breaks |

## 5. Utilities configuration audit

No Utilities configuration workbook exists.

| Source | Field | Current Type | Current Consumer | Proposed Target | Rule |
|---|---|---|---|---|---|
| Comparison Result GUI/request | Output Folder | Path | Reconciliation engine | `global_settings` or per-run `job_history.output_path_used` | Controlled by independent global-output flag |
| Comparison Result GUI/request | Start Date, End Date | Date | Readers/matcher | `global_settings` or per-run history | Controlled by independent global-period flag |
| Comparison Result GUI/request | Workflow, Source Mode, Attendance root, Outlook root | Text/path | Reconciliation request | Job history and `job_files` only | Per-run; do not invent persistent config |
| Attachment Consolidation GUI/request | Output Root | Path | Consolidation engine | Global output or per-run history | No period |
| Attachment Consolidation GUI/request | Mode, Workflow, Source Root, Scan Subfolders | Text/bool/path | Consolidation request | Job history only | Per-run |
| Outlook General | `TXT_Max_Lines` | INTEGER | Attachment Consolidation engine | `attachment_consolidation_settings.txt_max_lines` | Initial copy shown in preview |
| Attachment resolver | Configuration file path | Path | Locates Outlook workbook | Legacy compatibility only | Not a business setting |
| Merge TXT / Merge Excel | No active fields | — | Modules are empty | No schema table | Reassess only after real implementation exists |

## 6. Duplicate, typo, and development-data findings

### Duplicate/typo

1. Attendance `Payroll_Periode_From` appears twice; row 9 is logically the end
   date.
2. Both Outlook workbook filenames have identical hashes/content.
3. Outlook General data-validation ranges are shifted and conflicting.
4. Outlook HO sender validation incorrectly applies `Y/N` to the NIK column.
5. HRIS Browser validation combines boolean and channel values over one range.
6. HRIS `Reference` is required by the reader but its content is never read.
7. Attendance/HRIS Reference prose is not runtime configuration.
8. Several workbook parameters describe behavior that code currently hardcodes
   or does not consume. These are not activated in schema v1.

### Development/mock values requiring preview

- Attendance output and MDB paths point into development project folders.
- Attendance source names/codes include `Sample` records.
- HRIS URL points to a local `temp/hris_mock_site/login.html`.
- HRIS output points into the project output folder.
- HRIS default dates are fixed development dates.
- HRIS Run Control IDs/descriptions look like generic upload slots; ownership
  confirmation is required even though text formatting is correct.
- Outlook sender/required-CC rows contain personal Gmail test addresses.
- Outlook has active but otherwise blank sender rows; the reader silently skips
  them.
- Outlook payroll period and resubmit deadline are fixed legacy values.
- Outlook automatic reply is enabled and send mode is `SEND`; a safe migration
  preview must not activate outbound messaging without explicit confirmation.
- PIC/SPV summary recipient values are blank.

No credential or password was found in the audited workbook cells. Mailbox
addresses and SMTP host/port are operational settings, not credentials.
