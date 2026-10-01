from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path

import pytest
from openpyxl import Workbook

from shared.database import SQLiteConnectionFactory, SchemaManager
from shared.database.repositories import JobRepository
from utilities.att_data_repair.artifacts import AttDataRepairJobRequest
from utilities.att_data_repair.configuration import (
    AttDataRepairConfigurationService,
    AttDataRepairSettings,
)
from utilities.att_data_repair.constants import (
    INVALID_RECORDS_COLUMNS,
    VALID_RECORDS_COLUMNS,
)
from utilities.att_data_repair.engine import AttDataRepairEngine
from utilities.att_data_repair.job_audit import AttDataRepairJobAudit
from utilities.att_data_repair.models import AttDataRepairRequest
from utilities.att_data_repair.statuses import JobStatus
from utilities.att_data_repair.txt_writer import AttDataRepairTxtWriter


class FixedClock:
    def __call__(self) -> datetime:
        return datetime(2026, 8, 3, 9, 0, 0)


class CodeProvider:
    def __call__(self) -> int:
        return 4837


def test_typed_settings_adapter_maps_sqlite_to_job_request(
    tmp_path: Path,
) -> None:
    database = tmp_path / "settings.db"
    source = tmp_path / "source.xlsx"
    output = tmp_path / "output"
    output.mkdir()
    _write_source(source)
    SchemaManager().initialize_database(database, "test")
    with SQLiteConnectionFactory().connect(database) as connection:
        connection.execute(
            """
            UPDATE att_data_repair_settings
            SET minimum_duration_minutes = 75,
                weekday_default_in = '08:00',
                weekday_default_out = '16:30',
                saturday_missing_out_default = '11:15',
                midnight_time_out_default = '23:58',
                txt_max_rows = 500,
                generate_txt = 0,
                generate_excel_report = 1
            WHERE att_data_repair_settings_id = 1
            """
        )

    service = AttDataRepairConfigurationService()
    settings = service.read_settings(database)
    request = service.build_job_request(
        settings=settings,
        source_report=source,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        output_root=output,
    )

    assert settings.weekday_default_in == time(8, 0)
    assert request.analysis_request.minimum_duration_minutes == 75
    assert request.analysis_request.weekday_default_out == time(16, 30)
    assert request.analysis_request.saturday_missing_out_default == time(11, 15)
    assert request.analysis_request.midnight_time_out_default == time(23, 58)
    assert request.txt_max_rows_per_file == 500
    assert request.generate_txt is False
    assert request.generate_excel_report is True
    assert not hasattr(settings, "__dict__")


def test_disabled_settings_and_both_outputs_false_are_rejected() -> None:
    service = AttDataRepairConfigurationService()

    with pytest.raises(ValueError, match="disabled"):
        service.build_job_request(
            settings=AttDataRepairSettings(enabled=False),
            source_report="source.xlsx",
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            output_root="out",
        )

    with pytest.raises(ValueError, match="Minimal"):
        service.validate_settings(
            AttDataRepairSettings(generate_txt=False, generate_excel_report=False)
        )


@pytest.mark.parametrize(
    ("generate_txt", "generate_report", "expect_txt", "expect_report"),
    [
        (True, True, True, True),
        (True, False, True, False),
        (False, True, False, True),
    ],
)
def test_generate_flags_are_honored(
    tmp_path: Path,
    generate_txt: bool,
    generate_report: bool,
    expect_txt: bool,
    expect_report: bool,
) -> None:
    source = tmp_path / "source.xlsx"
    _write_source(source)
    engine = AttDataRepairEngine(
        txt_writer=AttDataRepairTxtWriter(CodeProvider()),
        clock=FixedClock(),
    )

    result = engine.run_job(
        AttDataRepairJobRequest(
            AttDataRepairRequest(source, date(2026, 8, 1), date(2026, 8, 31)),
            tmp_path,
            generate_txt=generate_txt,
            generate_excel_report=generate_report,
        )
    )

    payload = json.loads(result.paths.summary_json.read_text(encoding="utf-8"))
    assert result.status == JobStatus.SUCCESS
    assert bool(result.txt_artifacts) is expect_txt
    assert (result.report_artifact is not None) is expect_report
    assert payload["txt"]["generated"] is expect_txt
    assert payload["report"]["generated"] is expect_report


def test_run_job_rejects_both_outputs_false_before_output(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsx"
    _write_source(source)

    with pytest.raises(ValueError, match="Minimal"):
        AttDataRepairEngine(clock=FixedClock()).run_job(
            AttDataRepairJobRequest(
                AttDataRepairRequest(source, date(2026, 8, 1), date(2026, 8, 31)),
                tmp_path,
                generate_txt=False,
                generate_excel_report=False,
            )
        )

    assert not (tmp_path / "Utilities").exists()


def test_job_history_records_files_events_and_no_orphans(tmp_path: Path) -> None:
    database = tmp_path / "history.db"
    source = tmp_path / "source.xlsx"
    _write_source(source, invalid_nik=True)
    SchemaManager().initialize_database(database, "test")
    request = AttDataRepairJobRequest(
        AttDataRepairRequest(source, date(2026, 8, 1), date(2026, 8, 31)),
        tmp_path,
    )
    result = AttDataRepairEngine(
        txt_writer=AttDataRepairTxtWriter(CodeProvider()),
        clock=FixedClock(),
    ).run_job(request)

    job_pk = AttDataRepairJobAudit().record(database, request, result)

    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        repo = JobRepository(connection)
        job = repo.get_job_by_id(module_code="UTILITIES", job_id=result.job_id)
        files = repo.get_job_files(job_pk)
        events = repo.get_status_events(job_pk)
        orphan_files = connection.execute(
            """
            SELECT COUNT(*)
            FROM job_files f
            LEFT JOIN job_history h ON h.job_pk = f.job_pk
            WHERE h.job_pk IS NULL
            """
        ).fetchone()[0]
        orphan_events = connection.execute(
            """
            SELECT COUNT(*)
            FROM job_status_events e
            LEFT JOIN job_history h ON h.job_pk = e.job_pk
            WHERE h.job_pk IS NULL
            """
        ).fetchone()[0]

    assert job is not None
    assert job.feature_code == "Att Data Repair"
    assert job.unified_status == "COMPLETED_WITH_WARNING"
    assert job.success_count == 1
    assert job.warning_count == 1
    roles = [row["file_role"] for row in files]
    assert roles.count("HRIS_TXT") == 1
    assert "EXCEL_REPORT" in roles
    assert "PROCESS_LOG" in roles
    assert "SUMMARY_JSON" in roles
    phases = [row["phase"] for row in events]
    assert "STARTED" in phases
    assert "ANALYZED" in phases
    assert "TXT_GENERATED" in phases
    assert "REPORT_GENERATED" in phases
    assert "COMPLETED" in phases
    assert orphan_files == 0
    assert orphan_events == 0


def test_history_write_failure_does_not_delete_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = tmp_path / "history.db"
    source = tmp_path / "source.xlsx"
    _write_source(source)
    SchemaManager().initialize_database(database, "test")
    request = AttDataRepairJobRequest(
        AttDataRepairRequest(source, date(2026, 8, 1), date(2026, 8, 31)),
        tmp_path,
    )
    result = AttDataRepairEngine(
        txt_writer=AttDataRepairTxtWriter(CodeProvider()),
        clock=FixedClock(),
    ).run_job(request)

    def fail_add_file(self, record):
        raise RuntimeError("history failure")

    monkeypatch.setattr(JobRepository, "add_job_file", fail_add_file)
    ok = AttDataRepairJobAudit().safe_record(database, request, result)

    assert ok is False
    assert result.report_artifact.file_path.exists()
    assert result.paths.summary_json.exists()
    assert result.txt_artifacts[0].file_path.exists()
    assert "History write failed" in result.paths.process_log.read_text(encoding="utf-8")
    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM job_history").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM job_files").fetchone()[0] == 0


def _write_source(path: Path, *, invalid_nik: bool = False) -> None:
    workbook = Workbook()
    workbook.active.title = "Valid_Records"
    valid = workbook["Valid_Records"]
    invalid = workbook.create_sheet("Invalid_Records")
    valid.append(VALID_RECORDS_COLUMNS)
    invalid.append(INVALID_RECORDS_COLUMNS)
    valid.append(
        [
            1,
            "revision.xlsx",
            "nested/revision.xlsx",
            2,
            "HO",
            "000001234",
            "08/03/2026",
            "09:30",
            "08/03/2026",
            "17:00",
            "Outlook_Revisi_HO_001.txt",
            "VALID",
        ]
    )
    if invalid_nik:
        valid.append(
            [
                2,
                "revision.xlsx",
                "nested/revision.xlsx",
                3,
                "HO",
                "#REF!",
                "08/03/2026",
                "09:30",
                "08/03/2026",
                "17:00",
                "Outlook_Revisi_HO_001.txt",
                "VALID",
            ]
        )
    workbook.save(path)
    workbook.close()
