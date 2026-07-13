"""
Outlook - Revisi processing engine.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from outlook.downloader import OutlookComClient
from outlook.downloader import OutlookMessage
from outlook.parser import AttendanceRevisionRecord
from outlook.parser import OutlookAttachmentParser
from outlook.parser import OutlookDataAnomaly
from outlook.parser import OutlookTxtWriter
from outlook.report_writer import OutlookProcessReportWriter
from shared.config_manager import OutlookAttachmentRule
from shared.config_manager import OutlookReplyTemplate
from shared.config_manager import OutlookRevisiConfiguration
from shared.config_manager import OutlookRevisiConfigurationReader
from shared.config_manager import OutlookSenderConfig
from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class OutlookAttachmentProcessResult:
    """Report metadata for one saved Outlook attachment."""

    original_file_name: str
    saved_file_name: str
    path: Path
    file_extension: str
    file_size_kb: float
    file_status: str
    row_read: int = 0
    row_valid: int = 0
    row_anomaly: int = 0
    duplicate_row: int = 0
    empty_row_dropped: int = 0
    output_txt: list[Path] = field(default_factory=list)
    error_message: str = ""


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
    received_time: datetime | None = None
    sender_name: str = ""
    actual_cc: str = ""
    required_cc: str = ""
    expected_subject: str = ""
    detected_workflow: str = ""
    validation_sender: str = "NOT_CHECKED"
    validation_cc: str = "NOT_CHECKED"
    validation_subject: str = "NOT_CHECKED"
    validation_attachment: str = "NOT_CHECKED"
    validation_data: str = "NOT_CHECKED"
    failure_code: str = ""
    reply_result: str = "NOT_ATTEMPTED"
    reply_from: str = ""
    move_result: str = "NOT_REQUIRED"
    processed_time: datetime | None = None
    attachment_results: list[OutlookAttachmentProcessResult] = field(
        default_factory=list
    )
    attachment_count: int = 0
    valid_records: list[AttendanceRevisionRecord] = field(default_factory=list)
    anomalies: list[OutlookDataAnomaly] = field(default_factory=list)


@dataclass(slots=True)
class OutlookProcessResult:
    """Outlook - Revisi batch result."""

    success: bool
    job_id: str
    output_folder: Path
    total_email: int
    target_email: int
    skipped_other_workflow: int
    success_email: int
    failed_email: int
    output_txt_count: int
    message_results: list[OutlookProcessMessageResult]
    process_log: Path
    summary_json: Path
    workflow: str = ""
    start_time: datetime | None = None
    end_time: datetime | None = None
    report_folder: Path | None = None
    report_file: Path | None = None
    report_status: str = "NOT_ATTEMPTED"
    final_status: str = "COMPLETED"
    valid_row_count: int = 0
    anomaly_row_count: int = 0
    reconciliation_status: str = "PASS"
    reconciliation_issues: list[str] = field(default_factory=list)


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
        self.report_writer = OutlookProcessReportWriter()

    def run(self) -> OutlookProcessResult:
        """Run Outlook - Revisi processing."""
        start_time = datetime.now()
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
            total_email=len(message_results),
            target_email=len(message_results) - skipped_count,
            skipped_other_workflow=skipped_count,
            success_email=success_count,
            failed_email=failed_count,
            output_txt_count=output_txt_count,
            message_results=message_results,
            process_log=job_folder / "Process.log",
            summary_json=job_folder / "summary.json",
            workflow=self.workflow,
            start_time=start_time,
            end_time=datetime.now(),
            report_folder=report_folder,
            report_file=(
                report_folder
                / f"Outlook_Process_Report_{self.workflow}_{job_id}.xlsx"
            ),
        )
        result.valid_row_count = sum(
            len(item.valid_records) for item in message_results
        )
        result.anomaly_row_count = sum(
            len(item.anomalies) + sum(
                attachment.empty_row_dropped
                for attachment in item.attachment_results
            )
            for item in message_results
        )
        result.final_status = (
            "COMPLETED WITH WARNING"
            if failed_count or result.anomaly_row_count
            else "COMPLETED"
        )
        self._reconcile(result)
        self._write_artifacts(result)
        logger.info(
            "Outlook report generation started: %s", result.report_file
        )
        try:
            result.report_file = self.report_writer.write(result, configuration)
            result.report_status = "CREATED"
            logger.info("Outlook report generation succeeded: %s", result.report_file)
        except Exception as error:
            result.report_status = "FAILED"
            result.final_status = "COMPLETED WITH WARNING"
            result.reconciliation_issues.append(
                f"Report generation failed: {error}"
            )
            logger.exception("Outlook report generation failed; TXT output retained.")
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
        processed_time = datetime.now()

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
                received_time=message.received_time,
                sender_name=message.sender_name,
                actual_cc=message.cc,
                detected_workflow=detected_workflow,
                validation_sender="NOT_APPLICABLE",
                validation_cc="NOT_APPLICABLE",
                validation_subject="NOT_APPLICABLE",
                validation_attachment="NOT_APPLICABLE",
                validation_data="NOT_APPLICABLE",
                failure_code="OTHER_WORKFLOW",
                reply_result="NOT_REQUIRED",
                move_result="NOT_MOVED",
                processed_time=processed_time,
                attachment_count=(
                    message.attachment_count or len(message.attachments)
                ),
            )

        workflow = self.workflow
        sender = self._match_sender(configuration, message.sender_email, workflow)
        validation_sender = "PASS"
        validation_cc = "NOT_CHECKED"
        validation_subject = "NOT_CHECKED"
        failure_code = ""
        if sender is None:
            errors.append("Sender is not registered in sender master.")
            validation_sender = "FAIL"
            failure_code = "SENDER_NOT_REGISTERED"
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
                validation_cc = "FAIL"
                failure_code = failure_code or "CC_INVALID"
            else:
                validation_cc = "PASS"

        if sender is not None and not self._subject_matches(
            configuration,
            workflow,
            message.subject,
            sender,
        ):
            errors.append("Subject does not match configured subject rule.")
            validation_subject = "FAIL"
            failure_code = failure_code or "SUBJECT_INVALID"
        elif sender is not None:
            validation_subject = "PASS"

        attachment_paths = self._valid_attachment_paths(
            configuration,
            workflow,
            message,
            errors,
        )
        allowed_path_set = {path.resolve() for path in attachment_paths}
        attachment_results = [
            OutlookAttachmentProcessResult(
                original_file_name=attachment.file_name,
                saved_file_name=attachment.path.name,
                path=attachment.path,
                file_extension=attachment.path.suffix.lower(),
                file_size_kb=(
                    round(attachment.path.stat().st_size / 1024, 2)
                    if attachment.path.exists()
                    else 0
                ),
                file_status=(
                    "ACCEPTED"
                    if attachment.path.resolve() in allowed_path_set
                    else "REJECTED"
                ),
            )
            for attachment in message.attachments
        ]
        validation_attachment = "PASS" if attachment_paths else "FAIL"
        if not attachment_paths:
            failure_code = failure_code or "ATTACHMENT_INVALID"

        records: list[AttendanceRevisionRecord] = []
        anomalies: list[OutlookDataAnomaly] = []
        parse_attempted = not errors
        if parse_attempted:
            for attachment_path in attachment_paths:
                parse_result = self.parser.parse(attachment_path, workflow)
                records.extend(parse_result.records)
                errors.extend(parse_result.errors)
                anomalies.extend(parse_result.anomalies)
                attachment_result = next(
                    (
                        item for item in attachment_results
                        if item.path.resolve() == attachment_path.resolve()
                    ),
                    None,
                )
                if attachment_result is not None:
                    attachment_result.row_read = parse_result.row_read
                    attachment_result.row_valid = len(parse_result.records)
                    attachment_result.row_anomaly = len(parse_result.anomalies)
                    attachment_result.empty_row_dropped = (
                        parse_result.empty_row_dropped
                    )
                    if parse_result.errors:
                        attachment_result.file_status = "FAILED"
                        attachment_result.error_message = "\n".join(
                            parse_result.errors
                        )

            if not records and not errors:
                errors.append("No valid attendance rows found in attachment.")
                failure_code = failure_code or "NO_VALID_DATA"

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
            for attachment_result in attachment_results:
                attachment_result.output_txt = sorted(
                    {
                        record.output_file
                        for record in records
                        if record.source_file.resolve()
                        == attachment_result.path.resolve()
                        and record.output_file is not None
                    },
                    key=str,
                )

        else:
            for attachment_result in attachment_results:
                if attachment_result.file_status == "ACCEPTED":
                    attachment_result.file_status = "SKIPPED"
                    attachment_result.error_message = (
                        "Attachment processing was not attempted because email "
                        "validation failed."
                    )

        validation_data = (
            "PASS" if not errors and records else "FAIL"
        ) if parse_attempted else "NOT_CHECKED"
        if errors and not failure_code:
            failure_code = anomalies[0].code if anomalies else "VALIDATION_FAILED"

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
            received_time=message.received_time,
            sender_name=message.sender_name,
            actual_cc=message.cc,
            required_cc=sender.required_cc_email if sender else "",
            expected_subject=self._expected_subject(
                configuration, workflow, sender
            ) if sender else "",
            detected_workflow=detected_workflow,
            validation_sender=validation_sender,
            validation_cc=validation_cc,
            validation_subject=validation_subject,
            validation_attachment=validation_attachment,
            validation_data=validation_data,
            failure_code=failure_code,
            reply_from=str(
                configuration.general.get("Reply_From_SMTP", "")
            ),
            processed_time=processed_time,
            attachment_results=attachment_results,
            valid_records=records if status == "SUCCESS" else [],
            anomalies=anomalies,
            attachment_count=(
                message.attachment_count or len(message.attachments)
            ),
        )

        auto_reply = self._to_bool(
            configuration.general.get("Auto_Reply_Enabled")
        )
        send_mode = str(configuration.general.get("Send_Mode", "SEND")).upper()
        try:
            result.reply_sent = self._send_message_reply(
                configuration, client, message, result
            )
            if not auto_reply:
                result.reply_result = "NOT_REQUIRED"
            elif self.dry_run:
                result.reply_result = "NOT_ATTEMPTED"
            elif send_mode == "DRAFT":
                result.reply_result = "DRAFTED"
            elif result.reply_sent:
                result.reply_result = "SENT"
        except Exception as error:
            result.reply_result = "FAILED"
            result.status = "FAILED"
            result.failure_code = result.failure_code or "REPLY_FAILED"
            result.errors.append(f"Reply failed: {error}")
            logger.exception("Outlook reply failed for: %s", message.subject)

        if result.status == "SUCCESS" and result.reply_sent:
            processed_folder = str(
                configuration.general.get("Processed_Folder", "Deleted Items")
            )
            try:
                client.move_to_folder(message, processed_folder)
                result.move_result = "MOVED"
            except Exception as error:
                result.move_result = "FAILED"
                result.status = "FAILED"
                result.failure_code = result.failure_code or "MOVE_FAILED"
                result.errors.append(f"Move failed: {error}")
                logger.exception("Outlook move failed for: %s", message.subject)
        elif result.reply_result in {"DRAFTED", "NOT_ATTEMPTED"}:
            result.move_result = "NOT_MOVED"

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

    def _expected_subject(
        self,
        configuration: OutlookRevisiConfiguration,
        workflow: str,
        sender: OutlookSenderConfig,
    ) -> str:
        rule = next(
            (
                item for item in configuration.subject_rules
                if item.workflow == workflow
            ),
            None,
        )
        if rule is None:
            return ""
        return self._render_template(
            rule.subject_pattern,
            {
                "PERIOD": str(configuration.general.get("Payroll_Period", "")),
                "COMPANY": sender.company,
                "BRANCH_CODE": sender.branch_code,
            },
        )

    @staticmethod
    def _reconcile(result: OutlookProcessResult) -> None:
        issues: list[str] = []
        if result.total_email != result.target_email + result.skipped_other_workflow:
            issues.append("Email total does not match target plus skipped count.")
        if result.target_email != result.success_email + result.failed_email:
            issues.append("Target email does not match success plus failed count.")

        exported_records = sum(
            1
            for item in result.message_results
            for record in item.valid_records
            if record.output_file is not None
        )
        if result.valid_row_count != exported_records:
            issues.append("Valid row count does not match exported record count.")

        reply_sent = sum(
            1 for item in result.message_results if item.reply_result == "SENT"
        )
        moved = sum(
            1 for item in result.message_results if item.move_result == "MOVED"
        )
        if reply_sent > result.success_email + result.failed_email:
            issues.append("Reply sent count exceeds processed target email count.")
        if moved > reply_sent:
            issues.append("Moved email count exceeds sent reply count.")

        result.reconciliation_issues = issues
        result.reconciliation_status = "WARNING" if issues else "PASS"
        if issues:
            result.final_status = "COMPLETED WITH WARNING"

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
            f"Valid Rows   : {result.valid_row_count}",
            f"Anomaly Rows : {result.anomaly_row_count}",
            f"Report       : {result.report_status}",
            f"Report Path  : {result.report_file or ''}",
            f"Reconcile    : {result.reconciliation_status}",
            "",
            "REPORT GENERATION",
            f"- Started: {result.report_file or ''}",
            f"- Workflow: {result.workflow}",
            f"- Email results: {result.total_email}",
            f"- Attachment results: {sum(len(item.attachment_results) for item in result.message_results)}",
            f"- Valid rows: {result.valid_row_count}",
            f"- Anomaly rows: {result.anomaly_row_count}",
            f"- Output artifacts: {result.output_txt_count + 3}",
            f"- Reconciliation: {result.reconciliation_status}",
            f"- Result: {result.report_status}",
            "",
        ]

        if result.reconciliation_issues:
            lines.append("RECONCILIATION ISSUES")
            lines.extend(f"- {issue}" for issue in result.reconciliation_issues)
            lines.append("")

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
                    "total_email": result.total_email,
                    "target_email": result.target_email,
                    "skipped_other_workflow": result.skipped_other_workflow,
                    "success_email": result.success_email,
                    "failed_email": result.failed_email,
                    "output_txt_count": result.output_txt_count,
                    "report_file": str(result.report_file or ""),
                    "report_status": result.report_status,
                    "valid_row_count": result.valid_row_count,
                    "anomaly_row_count": result.anomaly_row_count,
                    "reconciliation_status": result.reconciliation_status,
                    "final_status": result.final_status,
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
                            "reply_result": item.reply_result,
                            "move_result": item.move_result,
                            "failure_code": item.failure_code,
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
