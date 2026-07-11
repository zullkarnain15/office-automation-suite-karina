"""
Outlook - Revisi processing engine.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from outlook.downloader import OutlookComClient
from outlook.downloader import OutlookMessage
from outlook.parser import AttendanceRevisionRecord
from outlook.parser import OutlookAttachmentParser
from outlook.parser import OutlookTxtWriter
from shared.config_manager import OutlookAttachmentRule
from shared.config_manager import OutlookReplyTemplate
from shared.config_manager import OutlookRevisiConfiguration
from shared.config_manager import OutlookRevisiConfigurationReader
from shared.config_manager import OutlookSenderConfig
from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class OutlookProcessMessageResult:
    """Result for one processed email."""

    entry_id: str
    subject: str
    sender_email: str
    workflow: str
    status: str
    errors: list[str]
    output_files: list[Path]
    reply_sent: bool


@dataclass(slots=True)
class OutlookProcessResult:
    """Outlook - Revisi batch result."""

    success: bool
    job_id: str
    output_folder: Path
    report_folder: Path
    total_email: int
    target_email: int
    skipped_other_workflow: int
    success_email: int
    failed_email: int
    output_txt_count: int
    message_results: list[OutlookProcessMessageResult]
    process_log: Path
    summary_json: Path


class OutlookRevisiEngine:
    """Process Outlook - Revisi messages using workbook configuration."""

    def __init__(
        self,
        configuration_file: str | Path,
        workflow: str,
        dry_run: bool = True,
        message_limit: int | None = None,
        client: OutlookComClient | None = None,
    ) -> None:
        self.configuration_file = Path(configuration_file)
        self.workflow = self._normalize_workflow(workflow)
        self.dry_run = dry_run
        self.message_limit = message_limit
        self.client = client
        self.parser = OutlookAttachmentParser()
        self.writer = OutlookTxtWriter()

    def run(self) -> OutlookProcessResult:
        """Run Outlook - Revisi processing."""
        configuration = OutlookRevisiConfigurationReader(
            self.configuration_file
        ).read()
        output_root = configuration.get_output_root()

        if output_root is None:
            raise ValueError("Output_Root is required in Outlook configuration.")

        job_id, job_folder = self._reserve_job_folder(output_root, self.workflow)
        attachments_folder = job_folder / "Attachments"
        txt_folder = job_folder / "TXT"
        report_folder = job_folder / "Report"
        for folder in (attachments_folder, txt_folder, report_folder):
            folder.mkdir(exist_ok=False)

        client = self.client or OutlookComClient(
            mailbox_smtp=str(configuration.general.get("Mailbox_SMTP", "")),
            source_folder=str(configuration.general.get("Source_Folder", "Inbox")),
            reply_from_smtp=str(
                configuration.general.get("Reply_From_SMTP", "")
                or configuration.general.get("Mailbox_SMTP", "")
            ),
        )

        messages = client.fetch_messages(
            attachment_folder=attachments_folder,
            limit=self.message_limit,
            message_filter=lambda message: bool(
                self._detect_message_workflow(configuration, message)
            ),
            attachment_filter=lambda message: self._detect_message_workflow(
                configuration, message
            ) == self.workflow,
        )
        history = self._load_history(output_root, self.workflow)
        message_results: list[OutlookProcessMessageResult] = []

        for message in messages:
            if self._message_key(message) in history:
                logger.info("Skipping duplicate Outlook message: %s", message.entry_id)
                continue

            result = self._process_message(
                configuration=configuration,
                client=client,
                message=message,
                job_folder=job_folder,
            )
            message_results.append(result)

            if result.status == "SUCCESS" and result.reply_sent:
                history.add(self._message_key(message))

        self._save_history(output_root, self.workflow, history)

        success_count = sum(1 for item in message_results if item.status == "SUCCESS")
        failed_count = sum(1 for item in message_results if item.status == "FAILED")
        skipped_count = sum(
            1 for item in message_results
            if item.status == "SKIPPED_OTHER_WORKFLOW"
        )
        output_txt_count = sum(len(item.output_files) for item in message_results)
        result = OutlookProcessResult(
            success=failed_count == 0,
            job_id=job_id,
            output_folder=job_folder,
            report_folder=report_folder,
            total_email=len(message_results),
            target_email=len(message_results) - skipped_count,
            skipped_other_workflow=skipped_count,
            success_email=success_count,
            failed_email=failed_count,
            output_txt_count=output_txt_count,
            message_results=message_results,
            process_log=job_folder / "Process.log",
            summary_json=job_folder / "summary.json",
        )

        self._write_artifacts(result)
        self._send_summary(configuration, client, result)
        return result

    @staticmethod
    def _reserve_job_folder(
        output_root: Path,
        workflow: str,
    ) -> tuple[str, Path]:
        """Reserve Output_Root/workflow/YYYYMMDD_HHMMSS atomically."""
        workflow_label = OutlookRevisiEngine._normalize_workflow(workflow)
        base_job_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        workflow_root = output_root / workflow_label

        for sequence in range(1, 1000):
            job_id = (
                base_job_id
                if sequence == 1
                else f"{base_job_id}_{sequence:02d}"
            )
            job_folder = workflow_root / job_id

            try:
                job_folder.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue

            return job_id, job_folder

        raise RuntimeError(
            f"Unable to reserve a unique Outlook job folder in {workflow_root}"
        )

    def _process_message(
        self,
        configuration: OutlookRevisiConfiguration,
        client: OutlookComClient,
        message: OutlookMessage,
        job_folder: Path,
    ) -> OutlookProcessMessageResult:
        errors: list[str] = []
        detected_workflow = self._detect_message_workflow(configuration, message)
        output_files: list[Path] = []

        if detected_workflow != self.workflow:
            logger.info(
                "Skipped email: %s | Reason: Email belongs to %s workflow",
                message.subject,
                detected_workflow or "another",
            )
            return OutlookProcessMessageResult(
                entry_id=message.entry_id,
                subject=message.subject,
                sender_email=message.sender_email,
                workflow=detected_workflow,
                status="SKIPPED_OTHER_WORKFLOW",
                errors=["Email belongs to another workflow."],
                output_files=[],
                reply_sent=False,
            )

        workflow = self.workflow
        sender = self._match_sender(configuration, message.sender_email, workflow)
        if sender is None:
            errors.append("Sender is not registered in sender master.")
        else:
            workflow = sender.workflow

        if sender is not None:
            missing_cc = self._missing_required_cc(sender.required_cc_email, message.cc)
            if missing_cc:
                actual_cc = message.cc or "(none)"
                errors.append(
                    "Required CC email is missing: "
                    + "; ".join(missing_cc)
                    + f". Actual CC resolved: {actual_cc}"
                )

        if sender is not None and not self._subject_matches(
            configuration,
            workflow,
            message.subject,
            sender,
        ):
            errors.append("Subject does not match configured subject rule.")

        attachment_paths = self._valid_attachment_paths(
            configuration,
            workflow,
            message,
            errors,
        )

        records: list[AttendanceRevisionRecord] = []
        if not errors:
            for attachment_path in attachment_paths:
                parse_result = self.parser.parse(attachment_path, workflow)
                records.extend(parse_result.records)
                errors.extend(parse_result.errors)

            if not records and not errors:
                errors.append("No valid attendance rows found in attachment.")

        if not errors:
            max_lines = self._to_int(
                configuration.general.get("TXT_Max_Lines"),
                default=10000,
            )
            output_files = self.writer.write(
                records=records,
                output_folder=job_folder / "TXT",
                workflow=workflow,
                max_lines=max_lines,
                job_id=job_folder.name,
            )

        status = "SUCCESS" if not errors else "FAILED"
        result = OutlookProcessMessageResult(
            entry_id=message.entry_id,
            subject=message.subject,
            sender_email=message.sender_email,
            workflow=workflow,
            status=status,
            errors=errors,
            output_files=output_files,
            reply_sent=False,
        )

        result.reply_sent = self._send_message_reply(
            configuration, client, message, result
        )

        if status == "SUCCESS" and result.reply_sent:
            processed_folder = str(
                configuration.general.get("Processed_Folder", "Deleted Items")
            )
            client.move_to_folder(message, processed_folder)

        return result

    def _match_sender(
        self,
        configuration: OutlookRevisiConfiguration,
        sender_email: str,
        workflow: str,
    ) -> OutlookSenderConfig | None:
        sender_email_lower = sender_email.strip().lower()
        senders = (
            configuration.ho_senders
            if workflow == "HO"
            else configuration.branch_senders
        )

        for sender in senders:
            if not sender.sender_email:
                continue
            if sender.sender_email.strip().lower() == sender_email_lower:
                return sender

        return None

    def _detect_message_workflow(
        self,
        configuration: OutlookRevisiConfiguration,
        message: OutlookMessage,
    ) -> str:
        """Classify before validation so other workflows can be safely skipped."""
        for workflow, senders in (
            ("HO", configuration.ho_senders),
            ("Branch", configuration.branch_senders),
        ):
            if any(
                self._subject_matches(
                    configuration, workflow, message.subject, sender
                )
                for sender in senders
            ):
                return workflow

        for workflow in ("HO", "Branch"):
            if self._match_sender(configuration, message.sender_email, workflow):
                return workflow

        return ""

    def _missing_required_cc(
        self,
        required_cc: str,
        actual_cc: str,
    ) -> list[str]:
        required = {
            email.lower()
            for email in OutlookRevisiConfigurationReader.split_emails(required_cc)
        }

        if not required:
            return []

        actual = actual_cc.lower()
        return [
            email
            for email in sorted(required)
            if email not in actual
        ]

    def _subject_matches(
        self,
        configuration: OutlookRevisiConfiguration,
        workflow: str,
        subject: str,
        sender: OutlookSenderConfig,
    ) -> bool:
        rules = [
            rule
            for rule in configuration.subject_rules
            if rule.workflow == workflow
        ]

        if not rules:
            return False

        values = {
            "PERIOD": str(configuration.general.get("Payroll_Period", "")),
            "COMPANY": sender.company,
            "BRANCH_CODE": sender.branch_code,
        }

        for rule in rules:
            pattern = self._subject_pattern_to_regex(
                rule.subject_pattern,
                values,
            )
            if re.search(pattern, subject, re.IGNORECASE):
                return True

        return False

    def _valid_attachment_paths(
        self,
        configuration: OutlookRevisiConfiguration,
        workflow: str,
        message: OutlookMessage,
        errors: list[str],
    ) -> list[Path]:
        if not workflow:
            return []

        rule = self._attachment_rule(configuration.attachment_rules, workflow)
        if rule is None:
            errors.append(f"Attachment rule not configured for workflow: {workflow}.")
            return []

        paths = [
            attachment.path
            for attachment in message.attachments
            if attachment.path.suffix.lower() in rule.allowed_extensions
        ]

        if not paths:
            errors.append(
                "No allowed attachment found. Allowed: "
                + "; ".join(rule.allowed_extensions)
            )

        return paths

    def _send_message_reply(
        self,
        configuration: OutlookRevisiConfiguration,
        client: OutlookComClient,
        message: OutlookMessage,
        result: OutlookProcessMessageResult,
    ) -> bool:
        if self._to_bool(configuration.general.get("Auto_Reply_Enabled")) is False:
            return False

        template = self._select_reply_template(configuration, result)
        if template is None:
            logger.warning("Reply template not found for result: %s", result.status)
            return False

        values = self._template_values(configuration, message, result)
        subject = self._render_template(template.subject_template, values)
        body = self._render_template(template.body_template, values)
        send_mode = str(configuration.general.get("Send_Mode", "SEND"))

        if self.dry_run:
            logger.info("Dry-run reply skipped: %s", subject)
            return False

        client.send_reply(
            message=message,
            subject=subject,
            body=body,
            send_mode=send_mode,
        )
        return send_mode.strip().upper() == "SEND"

    def _send_summary(
        self,
        configuration: OutlookRevisiConfiguration,
        client: OutlookComClient,
        result: OutlookProcessResult,
    ) -> None:
        template = next(
            (
                item
                for item in configuration.reply_templates
                if item.reply_code == "SUMMARY_PIC"
            ),
            None,
        )
        to = configuration.get_pic_hr_emails()

        if template is None or not to:
            return

        values = {
            "PERIOD": str(configuration.general.get("Payroll_Period", "")),
            "TOTAL_EMAIL": str(result.total_email),
            "SUCCESS_EMAIL": str(result.success_email),
            "FAILED_EMAIL": str(result.failed_email),
            "OUTPUT_TXT_COUNT": str(result.output_txt_count),
            "OUTPUT_FOLDER": str(result.output_folder),
        }
        subject = self._render_template(template.subject_template, values)
        body = self._render_template(template.body_template, values)

        if self.dry_run:
            logger.info("Dry-run summary skipped: %s", subject)
            return

        client.send_mail(
            to=to,
            cc=configuration.get_spv_pic_hr_emails(),
            subject=subject,
            body=body,
            send_mode=str(configuration.general.get("Send_Mode", "SEND")),
        )

    def _select_reply_template(
        self,
        configuration: OutlookRevisiConfiguration,
        result: OutlookProcessMessageResult,
    ) -> OutlookReplyTemplate | None:
        if result.status == "SUCCESS":
            code = "SUCCESS_SENDER"
        elif any("Required CC" in error for error in result.errors):
            code = "FAILED_CC"
        else:
            code = "FAILED_GENERAL"

        return next(
            (
                template
                for template in configuration.reply_templates
                if template.reply_code == code
            ),
            None,
        )

    def _template_values(
        self,
        configuration: OutlookRevisiConfiguration,
        message: OutlookMessage,
        result: OutlookProcessMessageResult,
    ) -> dict[str, str]:
        sender = (
            self._match_sender(
                configuration,
                message.sender_email,
                result.workflow,
            )
            if result.workflow in ("HO", "Branch")
            else None
        )
        return {
            "SENDER_NAME": message.sender_name,
            "PERIOD": str(configuration.general.get("Payroll_Period", "")),
            "ORIGINAL_SUBJECT": message.subject,
            "REQUIRED_CC_EMAIL": sender.required_cc_email if sender else "",
            "RESUBMIT_DEADLINE": str(
                configuration.general.get("Resubmit_Deadline", "")
            ),
            "ERROR_REASON": "\n".join(result.errors),
        }

    def _write_artifacts(self, result: OutlookProcessResult) -> None:
        lines = [
            "=" * 80,
            "Office Automation Suite - Karina",
            "Outlook - Revisi Process Log",
            "=" * 80,
            f"Job ID       : {result.job_id}",
            f"Output Folder: {result.output_folder}",
            f"Total Email  : {result.total_email}",
            f"Target Email : {result.target_email}",
            f"Skipped Other: {result.skipped_other_workflow}",
            f"Success      : {result.success_email}",
            f"Failed       : {result.failed_email}",
            "",
        ]

        for item in result.message_results:
            lines.append(f"[{item.status}] {item.sender_email} | {item.subject}")
            lines.append(f"Workflow: {item.workflow}")
            if item.errors:
                lines.extend(f"- {error}" for error in item.errors)
            for output_file in item.output_files:
                lines.append(f"TXT: {output_file}")
            lines.append("")

        result.process_log.write_text("\n".join(lines), encoding="utf-8")
        result.summary_json.write_text(
            json.dumps(
                {
                    "job_id": result.job_id,
                    "output_folder": str(result.output_folder),
                    "report_folder": str(result.report_folder),
                    "total_email": result.total_email,
                    "target_email": result.target_email,
                    "skipped_other_workflow": result.skipped_other_workflow,
                    "success_email": result.success_email,
                    "failed_email": result.failed_email,
                    "output_txt_count": result.output_txt_count,
                    "messages": [
                        {
                            "entry_id": item.entry_id,
                            "subject": item.subject,
                            "sender_email": item.sender_email,
                            "workflow": item.workflow,
                            "status": item.status,
                            "errors": item.errors,
                            "output_files": [
                                str(output_file)
                                for output_file in item.output_files
                            ],
                            "reply_sent": item.reply_sent,
                        }
                        for item in result.message_results
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _message_key(self, message: OutlookMessage) -> str:
        if message.entry_id:
            return message.entry_id

        return "|".join(
            [
                message.sender_email,
                message.subject,
                message.received_time.isoformat()
                if message.received_time is not None
                else "",
            ]
        )

    def _load_history(self, output_root: Path, workflow: str) -> set[str]:
        path = self._history_path(output_root, workflow)
        if not path.exists():
            return set()

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return set(data.get("processed_messages", []))
        except Exception:
            logger.warning("Runtime history could not be read: %s", path)
            return set()

    def _save_history(
        self,
        output_root: Path,
        workflow: str,
        history: set[str],
    ) -> None:
        path = self._history_path(output_root, workflow)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"processed_messages": sorted(history)},
                indent=2,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _history_path(output_root: Path, workflow: str) -> Path:
        workflow_label = OutlookRevisiEngine._normalize_workflow(workflow)
        return output_root / workflow_label / "runtime_history.json"

    @staticmethod
    def _normalize_workflow(workflow: str) -> str:
        normalized = str(workflow or "").strip().lower()
        if normalized == "ho":
            return "HO"
        if normalized == "branch":
            return "Branch"
        raise ValueError("workflow must be 'HO' or 'Branch'.")

    @staticmethod
    def _attachment_rule(
        rules: list[OutlookAttachmentRule],
        workflow: str,
    ) -> OutlookAttachmentRule | None:
        return next((rule for rule in rules if rule.workflow == workflow), None)

    @staticmethod
    def _subject_pattern_to_regex(
        pattern: str,
        values: dict[str, str],
    ) -> str:
        escaped = re.escape(pattern)

        for key, value in values.items():
            placeholder = re.escape("{" + key + "}")
            escaped = escaped.replace(placeholder, re.escape(value))

        escaped = re.sub(r"\\\{[A-Z_]+\\\}", r".+", escaped)
        return rf"^\s*{escaped}\s*$"

    @staticmethod
    def _render_template(template: str, values: dict[str, str]) -> str:
        result = template
        for key, value in values.items():
            result = result.replace("{" + key + "}", value)
        return result

    @staticmethod
    def _to_bool(value: Any) -> bool:
        return str(value or "").strip().lower() in {"y", "yes", "true", "1", "active"}

    @staticmethod
    def _to_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
