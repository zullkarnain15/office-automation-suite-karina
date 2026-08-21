from __future__ import annotations

from pathlib import Path
import pytest

from shared.database import SQLiteConnectionFactory, SchemaManager
from shared.database.models import JobHistoryRecord
from shared.database.repositories import GlobalSettingsRepository, JobRepository
from ui.attendance_models import (
    AttendanceCancellationToken,
    AttendanceOutputFile,
    AttendanceRunRequest,
    AttendanceRunResult,
    AttendanceValidationResult,
)
from ui.services.attendance_service import AttendanceService
from ui.services.protocols import StorageStatusView


class Storage:
    def __init__(self, root: Path, database: Path, valid=True):
        self.root, self.database, self.valid = root, database, valid

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


class Adapter:
    def __init__(self, result=None):
        self.result = result

    def validate_configuration(self, resolved):
        return AttendanceValidationResult(
            True,
            True,
            resolved.workflow,
            1,
            resolved.period_start,
            resolved.period_end,
            resolved.output_root,
            resolved.generate_txt,
            resolved.generate_report,
        )

    def run(self, resolved, **kwargs):
        return self.result


def database(tmp_path: Path) -> Path:
    path = tmp_path / "OAS-K.db"
    SchemaManager().initialize_database(path, "ui4")
    with SQLiteConnectionFactory().connect(path) as connection:
        GlobalSettingsRepository(connection).save_global_settings(
            output_root=str(tmp_path / "global-output"),
            period_start="2026-07-01",
            period_end="2026-07-31",
        )
        connection.execute(
            "INSERT INTO attendance_settings (attendance_settings_id, use_global_output, use_global_period, split_txt_rows, generate_report_default, default_workflow, updated_at) VALUES (1,1,1,10000,1,'HO','2026-07-01T00:00:00')"
        )
    return path


def request(config, output, **changes):
    values = dict(
        configuration_path=config,
        workflow="HO",
        use_global_output=False,
        use_global_period=False,
        override_output_root=output,
        override_period_start="2026-07-05",
        override_period_end="2026-07-06",
        generate_txt=True,
        generate_report=True,
    )
    values.update(changes)
    return AttendanceRunRequest(**values)


def test_database_unavailable_blocks_run_but_manual_validation_resolves(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    service = AttendanceService(
        Storage(tmp_path, tmp_path / "missing.db", False), Adapter()
    )
    raw = request(config, tmp_path / "output")
    assert service.resolve_request(raw, require_database=False).database_path is None
    with pytest.raises(RuntimeError, match="Data Location"):
        service.resolve_request(raw, require_database=True)
    assert not (tmp_path / "output").exists()


def test_normal_mode_resolves_sqlite_without_excel_path(tmp_path: Path) -> None:
    db = database(tmp_path)
    service = AttendanceService(Storage(tmp_path, db), Adapter())
    raw = request(None, tmp_path / "output")
    resolved = service.resolve_request(raw, require_database=True)
    assert resolved.configuration_path is None
    assert resolved.configuration_source == "SQLITE"


@pytest.mark.parametrize(
    "start,end",
    [(None, "2026-07-01"), ("07/01/2026", "2026-07-02"), ("2026-07-03", "2026-07-02")],
)
def test_period_validation(start, end, tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    service = AttendanceService(Storage(tmp_path, db), Adapter())
    with pytest.raises(ValueError):
        service.resolve_request(
            request(
                config, tmp_path, override_period_start=start, override_period_end=end
            ),
            require_database=True,
        )


def test_global_and_manual_resolution_do_not_mutate_settings(tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    service = AttendanceService(Storage(tmp_path, db), Adapter())
    global_value = service.resolve_request(
        request(config, tmp_path, use_global_output=True, use_global_period=True),
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
    assert manual.output_root == tmp_path / "manual"
    with SQLiteConnectionFactory().connect(db, read_only=True) as connection:
        saved = GlobalSettingsRepository(connection).get_global_settings()
    assert saved.output_root == str(tmp_path / "global-output")


def test_workflow_and_output_options_validation(tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    service = AttendanceService(Storage(tmp_path, db), Adapter())
    assert (
        service.resolve_request(
            request(config, tmp_path, workflow="BRANCH"), require_database=True
        ).workflow
        == "BRANCH"
    )
    with pytest.raises(ValueError, match="Minimal"):
        service.resolve_request(
            request(config, tmp_path, generate_txt=False, generate_report=False),
            require_database=True,
        )


def test_job_lifecycle_and_existing_files_are_recorded(tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    folder = tmp_path / "job"
    folder.mkdir()
    txt = folder / "one.txt"
    txt.touch()
    missing = folder / "missing.xlsx"
    resolved_service = AttendanceService(Storage(tmp_path, db), Adapter())
    resolved = resolved_service.resolve_request(
        request(config, tmp_path), require_database=True
    )
    result = AttendanceRunResult(
        True,
        False,
        resolved.job_id,
        "HO",
        "2026-07-01T00:00:00+00:00",
        "2026-07-01T00:00:01+00:00",
        tmp_path,
        folder,
        (
            AttendanceOutputFile("HRIS_TXT", txt),
            AttendanceOutputFile("EXCEL_REPORT", missing),
        ),
        {"raw": 2, "valid": 1, "anomaly": 1},
        process_log_path=None,
        summary_json_path=None,
    )
    resolved_service.adapter.result = result
    returned = resolved_service.run_job(
        resolved,
        cancellation=AttendanceCancellationToken(),
        progress=lambda event: None,
        log=lambda event: None,
    )
    assert returned.success
    with SQLiteConnectionFactory().connect(db, read_only=True) as connection:
        job = connection.execute(
            "SELECT * FROM job_history WHERE job_id=?", (resolved.job_id,)
        ).fetchone()
        events = connection.execute(
            "SELECT unified_status FROM job_status_events WHERE job_pk=? ORDER BY status_event_id",
            (job["job_pk"],),
        ).fetchall()
        files = connection.execute(
            "SELECT file_role FROM job_files WHERE job_pk=?", (job["job_pk"],)
        ).fetchall()
    assert job["unified_status"] == "COMPLETED"
    assert [row[0] for row in events] == ["PENDING", "RUNNING", "COMPLETED"]
    assert [row[0] for row in files] == ["HRIS_TXT"]
    assert job["output_path_used"] == str(tmp_path)
    assert job["period_start_used"] == "2026-07-05"
    assert not job["used_global_output"] and not job["used_global_period"]


def test_failed_and_cancel_request_statuses(tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    service = AttendanceService(Storage(tmp_path, db), Adapter())
    resolved = service.resolve_request(request(config, tmp_path), require_database=True)
    service.adapter.result = AttendanceRunResult(
        False,
        True,
        resolved.job_id,
        "HO",
        "2026-07-01T00:00:00+00:00",
        "2026-07-01T00:00:01+00:00",
        tmp_path,
        None,
        (),
        {},
        error_summary="cancelled",
    )
    token = AttendanceCancellationToken()
    # The PENDING record is created by run_job; final state must be controlled.
    service.run_job(
        resolved,
        cancellation=token,
        progress=lambda event: None,
        log=lambda event: None,
    )
    with SQLiteConnectionFactory().connect(db, read_only=True) as connection:
        assert (
            connection.execute(
                "SELECT unified_status FROM job_history WHERE job_id=?",
                (resolved.job_id,),
            ).fetchone()[0]
            == "CANCELLED"
        )


def test_failed_run_records_error_and_failed_status(tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    service = AttendanceService(Storage(tmp_path, db), Adapter())
    resolved = service.resolve_request(request(config, tmp_path), require_database=True)
    service.adapter.result = AttendanceRunResult(
        False,
        False,
        resolved.job_id,
        "HO",
        "2026-07-01T00:00:00+00:00",
        "2026-07-01T00:00:01+00:00",
        tmp_path,
        None,
        (),
        {"anomaly": 2},
        error_summary="fixture engine failure",
    )

    service.run_job(
        resolved,
        cancellation=AttendanceCancellationToken(),
        progress=lambda event: None,
        log=lambda event: None,
    )

    with SQLiteConnectionFactory().connect(db, read_only=True) as connection:
        job = connection.execute(
            "SELECT unified_status, error_message, failed_count "
            "FROM job_history WHERE job_id=?",
            (resolved.job_id,),
        ).fetchone()
    assert tuple(job) == ("FAILED", "fixture engine failure", 2)


def test_unexpected_adapter_error_is_normalized_and_finalized(tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)

    class RaisingAdapter(Adapter):
        def run(self, resolved, **kwargs):
            raise RuntimeError("adapter exploded")

    service = AttendanceService(Storage(tmp_path, db), RaisingAdapter())
    resolved = service.resolve_request(request(config, tmp_path), require_database=True)
    log_events = []
    result = service.run_job(
        resolved,
        cancellation=AttendanceCancellationToken(),
        progress=lambda event: None,
        log=log_events.append,
    )

    assert not result.success
    assert result.error_summary == "adapter exploded"
    assert log_events[-1].level == "ERROR"
    with SQLiteConnectionFactory().connect(db, read_only=True) as connection:
        status = connection.execute(
            "SELECT unified_status FROM job_history WHERE job_id=?",
            (resolved.job_id,),
        ).fetchone()[0]
    assert status == "FAILED"


def test_cancel_request_records_controlled_status_event(tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    service = AttendanceService(Storage(tmp_path, db), Adapter())
    resolved = service.resolve_request(request(config, tmp_path), require_database=True)
    with SQLiteConnectionFactory().connect(db) as connection:
        JobRepository(connection).create_job(
            JobHistoryRecord(
                job_id=resolved.job_id,
                module_code="ATTENDANCE",
                workflow="HO",
                unified_status="RUNNING",
                output_path_used=str(tmp_path),
                used_global_output=False,
                used_global_period=False,
                created_at="2026-07-01T00:00:00+00:00",
            )
        )
    token = AttendanceCancellationToken()

    service.request_cancellation(resolved, token)

    assert token.requested
    with SQLiteConnectionFactory().connect(db, read_only=True) as connection:
        event = connection.execute(
            "SELECT unified_status, legacy_status, phase "
            "FROM job_status_events WHERE legacy_status='CANCEL_REQUESTED'"
        ).fetchone()
    assert tuple(event) == ("PAUSED", "CANCEL_REQUESTED", "CANCEL_REQUESTED")


def test_late_cancel_request_does_not_overwrite_terminal_status(tmp_path: Path) -> None:
    config = tmp_path / "config.xlsx"
    config.touch()
    db = database(tmp_path)
    service = AttendanceService(Storage(tmp_path, db), Adapter())
    resolved = service.resolve_request(request(config, tmp_path), require_database=True)
    with SQLiteConnectionFactory().connect(db) as connection:
        repository = JobRepository(connection)
        repository.create_job(
            JobHistoryRecord(
                job_id=resolved.job_id,
                module_code="ATTENDANCE",
                workflow="HO",
                unified_status="RUNNING",
                output_path_used=str(tmp_path),
                used_global_output=False,
                used_global_period=False,
                created_at="2026-07-01T00:00:00+00:00",
            )
        )
        repository.finish_job(
            module_code="ATTENDANCE",
            job_id=resolved.job_id,
            unified_status="CANCELLED",
        )

    service.request_cancellation(resolved, AttendanceCancellationToken())

    with SQLiteConnectionFactory().connect(db, read_only=True) as connection:
        job = connection.execute(
            "SELECT unified_status FROM job_history WHERE job_id=?",
            (resolved.job_id,),
        ).fetchone()
        late_events = connection.execute(
            "SELECT COUNT(*) FROM job_status_events "
            "WHERE job_pk=(SELECT job_pk FROM job_history WHERE job_id=?) "
            "AND legacy_status='CANCEL_REQUESTED'",
            (resolved.job_id,),
        ).fetchone()[0]
    assert job[0] == "CANCELLED"
    assert late_events == 0
