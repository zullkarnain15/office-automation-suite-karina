from pathlib import Path

from openpyxl import Workbook

from outlook.downloader import OutlookAttachment
from outlook.downloader import OutlookMessage
from outlook.engine import OutlookRevisiEngine
from outlook.parser import OutlookAttachmentParser


def _configuration(path: Path, output_root: Path) -> None:
    workbook = Workbook()
    workbook.active.title = "General"
    for name in (
        "HO_Sender_Master",
        "Branch_Sender_Master",
        "Subject_Rules",
        "Attachment_Rules",
        "Validation_Rules",
        "Reply_Templates",
    ):
        workbook.create_sheet(name)

    workbook["General"].append(["Title"])
    workbook["General"].append([])
    workbook["General"].append([])
    workbook["General"].append(["Parameter", "Value", "Description"])
    workbook["General"].append(["Integration_Method", "OOM_COM", ""])
    workbook["General"].append(["Mailbox_SMTP", "karina.hr.1@oto.co.id", ""])
    workbook["General"].append(["Source_Folder", "Inbox", ""])
    workbook["General"].append(["Reply_From_SMTP", "karina.hr.1@oto.co.id", ""])
    workbook["General"].append(["Output_Root", str(output_root), ""])
    workbook["General"].append(["Payroll_Period", "06-2026", ""])
    workbook["General"].append(["Auto_Reply_Enabled", "TRUE", ""])
    workbook["General"].append(["Send_Mode", "DRAFT", ""])
    workbook["General"].append(["TXT_Max_Lines", "1", ""])

    workbook["HO_Sender_Master"].append(["Title"])
    workbook["HO_Sender_Master"].append([])
    workbook["HO_Sender_Master"].append([])
    workbook["HO_Sender_Master"].append(
        ["Active", "Sender_Name", "Sender_Email", "Required_CC_Email"]
    )
    workbook["HO_Sender_Master"].append(
        ["Y", "HO User", "ho@example.com", "cc@example.com"]
    )

    workbook["Branch_Sender_Master"].append(["Title"])
    workbook["Branch_Sender_Master"].append([])
    workbook["Branch_Sender_Master"].append([])
    workbook["Branch_Sender_Master"].append(
        [
            "Active",
            "Company",
            "Branch_Code",
            "Sender_Name",
            "Sender_Email",
            "Required_CC_Email",
        ]
    )

    workbook["Subject_Rules"].append(["Title"])
    workbook["Subject_Rules"].append([])
    workbook["Subject_Rules"].append([])
    workbook["Subject_Rules"].append(["Active", "Workflow", "Subject_Pattern"])
    workbook["Subject_Rules"].append(["Y", "HO", "ATT_REV {PERIOD}"])

    workbook["Attachment_Rules"].append(["Title"])
    workbook["Attachment_Rules"].append([])
    workbook["Attachment_Rules"].append([])
    workbook["Attachment_Rules"].append(["Active", "Workflow", "Allowed_Extensions"])
    workbook["Attachment_Rules"].append(["Y", "HO", ".xlsx;.xls"])

    workbook["Validation_Rules"].append(["Title"])
    workbook["Validation_Rules"].append([])
    workbook["Validation_Rules"].append([])
    workbook["Validation_Rules"].append(["Active", "Rule_Code", "Workflow", "Rule_Value"])
    workbook["Validation_Rules"].append(["Y", "NIK_REQUIRED", "All", "TRUE"])

    workbook["Reply_Templates"].append(["Title"])
    workbook["Reply_Templates"].append([])
    workbook["Reply_Templates"].append([])
    workbook["Reply_Templates"].append(
        [
            "Active",
            "Reply_Code",
            "Recipient_Type",
            "Trigger",
            "Subject_Template",
            "Body_Template",
        ]
    )
    workbook["Reply_Templates"].append(
        ["Y", "SUCCESS_SENDER", "SENDER", "PROCESS_SUCCESS", "Re: {ORIGINAL_SUBJECT}", "OK"]
    )
    workbook["Reply_Templates"].append(
        ["Y", "FAILED_CC", "SENDER", "CC_INVALID", "Re: {ORIGINAL_SUBJECT}", "CC BAD"]
    )
    workbook["Reply_Templates"].append(
        ["Y", "FAILED_GENERAL", "SENDER", "VALIDATION_FAILED", "Re: {ORIGINAL_SUBJECT}", "{ERROR_REASON}"]
    )

    workbook.save(path)


def _ho_attachment(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["NIK", "DATE IN", "TIME IN", "DATE OUT", "TIMEOUT"])
    sheet.append(["123456789", "06/01/2026", "08:00", "06/01/2026", "17:00"])
    sheet.append(["987654321", "06/02/2026", "09:00", "06/02/2026", "18:00"])
    workbook.save(path)


class FakeClient:
    def __init__(self, messages):
        self.messages = messages
        self.replies = []

    def fetch_messages(self, attachment_folder, limit=None):
        return self.messages[:limit]

    def send_reply(self, **kwargs):
        self.replies.append(kwargs)

    def send_mail(self, **kwargs):
        self.replies.append(kwargs)

    def move_to_folder(self, message, folder_name):
        return None


def test_parse_ho_excel_attachment(tmp_path: Path) -> None:
    attachment = tmp_path / "attendance.xlsx"
    _ho_attachment(attachment)

    result = OutlookAttachmentParser().parse_ho_excel(attachment)

    assert result.valid
    assert len(result.records) == 2
    assert result.records[0].to_txt_row() == [
        "06/01/2026",
        "123456789",
        "06/01/2026",
        "08:00",
        "06/01/2026",
        "17:00",
    ]


def test_engine_writes_split_txt_in_dry_run(tmp_path: Path) -> None:
    config_path = tmp_path / "config.xlsx"
    output_root = tmp_path / "output" / "Outlook-Revisi"
    attachment = tmp_path / "attendance.xlsx"
    _configuration(config_path, output_root)
    _ho_attachment(attachment)
    message = OutlookMessage(
        entry_id="entry-1",
        store_id="store",
        subject="ATT_REV 06-2026",
        sender_name="HO User",
        sender_email="ho@example.com",
        cc="cc@example.com",
        received_time=None,
        attachments=[
            OutlookAttachment(
                file_name=attachment.name,
                path=attachment,
            )
        ],
    )
    client = FakeClient([message])

    result = OutlookRevisiEngine(
        configuration_file=config_path,
        dry_run=True,
        client=client,
    ).run()

    assert result.success
    assert result.success_email == 1
    assert result.output_txt_count == 2
    assert all(path.exists() for path in result.message_results[0].output_files)
    assert client.replies == []
