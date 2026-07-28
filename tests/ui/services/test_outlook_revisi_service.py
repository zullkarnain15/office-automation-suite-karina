from __future__ import annotations

from pathlib import Path

import pytest

from shared.database import SchemaManager, SQLiteConnectionFactory
from shared.database.models import JobHistoryRecord
from shared.database.repositories import GlobalSettingsRepository, JobRepository
from ui.outlook_revisi_models import (
    MailboxValidationResult,
    OutboundSafetyState,
    OutlookRevisiCancellationToken,
    OutlookRevisiOutputFile,
    OutlookRevisiRunRequest,
    OutlookRevisiRunResult,
    OutlookRevisiValidationResult,
)
from ui.services.outlook_revisi_service import OutlookRevisiService
from ui.services.protocols import StorageStatusView


class Storage:
    def __init__(self, root: Path, database: Path, valid=True):
        self.root = root
        self.database = database
        self.valid = valid

    def resolve_status(self):
        return StorageStatusView(
            "READY" if self.valid else "INITIAL_SETUP_REQUIRED",
            self.root,
            self.database,
            self.database.exists(),
            self.valid,
            1 if self.valid else None,
            "test",
            "Tersedia",
            self.root / "profiles",
            self.root / "backup",
            self.root / "output",
            self.root / "logs",
            self.root / "diagnostics",
        )


def validation(resolved, *, requires_confirmation=False):
    return OutlookRevisiValidationResult(
        True,
        True,
        resolved.workflow,
        resolved.period_start,
        resolved.period_end,
        resolved.output_root,
        MailboxValidationResult(
            True,
            "karina.hr.1@oto.co.id",
            "Inbox",
            "READY",
            True,
            True,
            "RPA.HR01",
        ),
        OutboundSafetyState(
            True,
            "SEND",
            "SEND" if requires_confirmation else "PREVIEW",
            True,
            False,
            requires_confirmation=requires_confirmation,
        ),
        sender_count=1,
        subject_rule_count=1,
        attachment_rule_count=1,
        validation_rule_count=1,
        reply_template_count=1,
    )


class Adapter:
    def __init__(self, result=None, *, requires_confirmation=False):
        self.result = result
        self.requires_confirmation = requires_confirmation

    def validate(self, resolved, **kwargs):
        return validation(
            resolved,
            requires_confirmation=self.requires_confirmation,
        )

    def run(self, resolved, **kwargs):
        return self.result


def database(tmp_path: Path) -> Path:
    path = tmp_path / "OAS-K.db"
    SchemaManager().initialize_database(path, "ui5")
    with SQLiteConnectionFactory().connect(path) as connection:
        GlobalSettingsRepository(connection).save_global_settings(
            output_root=str(tmp_path / "global-output"),
            period_start="2026-07-01",
            period_end="2026-07-31",
        )
        connection.execute(
            "INSERT INTO outlook_settings ("
            "outlook_settings_id, use_global_output, use_global_period, "
            "mailbox_smtp, payroll_period, updated_at"
            ") VALUES (1, 1, 1, 'karina.hr.1@oto.co.id', "
            "'07-2026', '2026-07-01')"
        )
    return path


def request(config: Path, output: Path, **changes):
    values = dict(
        configuration_path=config,
        workflow="HO",
        use_global_output=False,
        use_global_period=False,
        override_output_root=output,
        override_period_start="2026-07-05",
        override_period_end="2026-07-06",
        dry_run=True,
        message_limit=25,
    )
    values.update(changes)
    return OutlookRevisiRunRequest(**values)


def test_database_unavailable_blocks_run_but_manual_validation_resolves(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    service = OutlookRevisiService(
        Storage(tmp_path, tmp_path / "missing.db", False), Adapter()
    )
    raw = request(config, tmp_path / "output")

    assert service.resolve_request(raw, require_database=False).database_path is None
    with pytest.raises(RuntimeError, match="Data Location"):
        service.resolve_request(raw, require_database=True)
    assert not (tmp_path / "output").exists()


def test_normal_mode_resolves_sqlite_without_excel_path(tmp_path: Path) -> None:
    db = database(tmp_path)
    service = OutlookRevisiService(Storage(tmp_path, db), Adapter())
    resolved = service.resolve_request(
        request(None, tmp_path / "output"), require_database=True
    )
    assert resolved.configuration_path is None
    assert resolved.configuration_source == "SQLITE"


@pytest.mark.parametrize(
    "payroll_period",
    [
        "7-2026",
        "13-2026",
        "2026-07",
        "07/2026",
    ],
)
def test_payroll_period_validation(payroll_period, tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    service = OutlookRevisiService(Storage(tmp_path, db), Adapter())
    with pytest.raises(ValueError):
        service.resolve_request(
            request(
                config,
                tmp_path,
                payroll_period=payroll_period,
            ),
            require_database=True,
        )


def test_global_and_manual_resolution_do_not_mutate_settings(tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    service = OutlookRevisiService(Storage(tmp_path, db), Adapter())
    global_value = service.resolve_request(
        request(
            config,
            tmp_path,
            use_global_output=True,
            use_global_period=True,
        ),
        require_database=True,
    )
    manual = service.resolve_request(
        request(config, tmp_path / "manual"), require_database=True
    )

    assert global_value.output_root == tmp_path / "global-output"
    assert (global_value.period_start, global_value.period_end) == (
        "2026-07-01",
        "2026-07-31",
    )
    assert global_value.payroll_period == "07-2026"
    assert manual.output_root == tmp_path / "manual"
    with SQLiteConnectionFactory().connect(db, read_only=True) as connection:
        saved = GlobalSettingsRepository(connection).get_global_settings()
    assert saved.output_root == str(tmp_path / "global-output")


def test_workflow_limit_and_outbound_confirmation(tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    adapter = Adapter(requires_confirmation=True)
    service = OutlookRevisiService(Storage(tmp_path, db), adapter)
    resolved, value = service.preflight(
        request(config, tmp_path, workflow="BRANCH", dry_run=False),
        require_database=True,
        check_mailbox=True,
    )
    assert resolved.workflow == "BRANCH"
    assert resolved.outbound_requires_confirmation
    with pytest.raises(ValueError, match="checkbox"):
        service.confirm_outbound(
            resolved, value.outbound, acknowledged=False, typed_confirmed=True
        )
    with pytest.raises(ValueError, match="SEND"):
        service.confirm_outbound(
            resolved, value.outbound, acknowledged=True, typed_confirmed=False
        )
    confirmed = service.confirm_outbound(
        resolved, value.outbound, acknowledged=True, typed_confirmed=True
    )
    assert confirmed.outbound_acknowledged and confirmed.send_typed_confirmed
    with pytest.raises(ValueError, match="Email Limit"):
        service.resolve_request(
            request(config, tmp_path, message_limit=0), require_database=True
        )


def test_job_lifecycle_actual_values_and_existing_files(tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    folder = tmp_path / "job"
    attachments = folder / "Attachments"
    attachments.mkdir(parents=True)
    txt = folder / "one.txt"
    report = folder / "report.xlsx"
    process_log = folder / "Process.log"
    summary = folder / "summary.json"
    for item in (txt, report, process_log, summary):
        item.touch()
    missing = folder / "missing.txt"
    service = OutlookRevisiService(Storage(tmp_path, db), Adapter())
    resolved = service.resolve_request(request(config, tmp_path), require_database=True)
    service.adapter.result = OutlookRevisiRunResult(
        True,
        False,
        resolved.job_id,
        "HO",
        "karina.hr.1@oto.co.id",
        "2026-07-01T00:00:00+00:00",
        "2026-07-01T00:00:01+00:00",
        tmp_path,
        folder,
        {"total": 2, "success": 1, "failed": 0, "skipped": 1},
        {"total": 1, "accepted": 1, "rejected": 0},
        {"sent": 0, "drafted": 0, "failed": 0},
        (
            OutlookRevisiOutputFile("OUTPUT_FOLDER", folder),
            OutlookRevisiOutputFile("ATTACHMENT_FOLDER", attachments),
            OutlookRevisiOutputFile("HRIS_TXT", txt),
            OutlookRevisiOutputFile("EXCEL_REPORT", report),
            OutlookRevisiOutputFile("PROCESS_LOG", process_log),
            OutlookRevisiOutputFile("SUMMARY_JSON", summary),
            OutlookRevisiOutputFile("HRIS_TXT", missing),
        ),
        process_log_path=process_log,
        summary_json_path=summary,
        attachment_folder=attachments,
    )

    service.run_job(
        resolved,
        cancellation=OutlookRevisiCancellationToken(),
        progress=lambda event: None,
        log=lambda event: None,
    )

    with SQLiteConnectionFactory().connect(db, read_only=True) as connection:
        job = connection.execute(
            "SELECT * FROM job_history WHERE job_id=?", (resolved.job_id,)
        ).fetchone()
        events = connection.execute(
            "SELECT unified_status FROM job_status_events "
            "WHERE job_pk=? ORDER BY status_event_id",
            (job["job_pk"],),
        ).fetchall()
        files = connection.execute(
            "SELECT file_role FROM job_files WHERE job_pk=? ORDER BY job_file_id",
            (job["job_pk"],),
        ).fetchall()
    assert job["unified_status"] == "COMPLETED"
    assert [row[0] for row in events] == ["PENDING", "RUNNING", "COMPLETED"]
    assert [row[0] for row in files] == [
        "OUTPUT_FOLDER",
        "ATTACHMENT_FOLDER",
        "HRIS_TXT",
        "EXCEL_REPORT",
        "PROCESS_LOG",
        "SUMMARY_JSON",
    ]
    assert job["output_path_used"] == str(tmp_path)
    assert job["period_start_used"] == "2026-07-01"
    assert not job["used_global_output"] and not job["used_global_period"]


@pytest.mark.parametrize(
    "cancelled,success,expected",
    [(False, False, "FAILED"), (True, False, "CANCELLED")],
)
def test_failed_and_cancelled_jobs_are_terminal(
    cancelled, success, expected, tmp_path: Path
) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    service = OutlookRevisiService(Storage(tmp_path, db), Adapter())
    resolved = service.resolve_request(request(config, tmp_path), require_database=True)
    service.adapter.result = OutlookRevisiRunResult(
        success,
        cancelled,
        resolved.job_id,
        "HO",
        "karina.hr.1@oto.co.id",
        "2026-07-01T00:00:00+00:00",
        "2026-07-01T00:00:01+00:00",
        tmp_path,
        None,
        {"failed": 1},
        {},
        {},
        (),
        error_summary="fixture failure",
    )
    service.run_job(
        resolved,
        cancellation=OutlookRevisiCancellationToken(),
        progress=lambda event: None,
        log=lambda event: None,
    )
    with SQLiteConnectionFactory().connect(db, read_only=True) as connection:
        job = connection.execute(
            "SELECT unified_status, error_message FROM job_history WHERE job_id=?",
            (resolved.job_id,),
        ).fetchone()
    assert tuple(job) == (expected, "fixture failure")


def test_cancel_request_and_late_cancel_guard(tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    service = OutlookRevisiService(Storage(tmp_path, db), Adapter())
    resolved = service.resolve_request(request(config, tmp_path), require_database=True)
    with SQLiteConnectionFactory().connect(db) as connection:
        repository = JobRepository(connection)
        repository.create_job(
            JobHistoryRecord(
                job_id=resolved.job_id,
                module_code="OUTLOOK_REVISI",
                workflow="HO",
                unified_status="RUNNING",
                output_path_used=str(tmp_path),
                used_global_output=False,
                used_global_period=False,
                created_at="2026-07-01T00:00:00+00:00",
            )
        )
    token = OutlookRevisiCancellationToken()
    service.request_cancellation(resolved, token)
    assert token.requested
    with SQLiteConnectionFactory().connect(db) as connection:
        row = connection.execute(
            "SELECT unified_status, legacy_status FROM job_history WHERE job_id=?",
            (resolved.job_id,),
        ).fetchone()
        assert tuple(row) == ("PAUSED", "CANCEL_REQUESTED")
        JobRepository(connection).finish_job(
            module_code="OUTLOOK_REVISI",
            job_id=resolved.job_id,
            unified_status="CANCELLED",
        )
    service.request_cancellation(resolved, OutlookRevisiCancellationToken())
    with SQLiteConnectionFactory().connect(db, read_only=True) as connection:
        status = connection.execute(
            "SELECT unified_status FROM job_history WHERE job_id=?",
            (resolved.job_id,),
        ).fetchone()[0]
    assert status == "CANCELLED"
