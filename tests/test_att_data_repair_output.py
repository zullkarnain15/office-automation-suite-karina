from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path

import pytest
from openpyxl import Workbook

from utilities.att_data_repair.artifacts import AttDataRepairJobRequest
from utilities.att_data_repair.constants import (
    INVALID_RECORDS_COLUMNS,
    VALID_RECORDS_COLUMNS,
)
from utilities.att_data_repair.engine import AttDataRepairEngine
from utilities.att_data_repair.job_manager import AttDataRepairJobManager
from utilities.att_data_repair.models import AttDataRepairRequest, FinalRecord
from utilities.att_data_repair.statuses import JobStatus
from utilities.att_data_repair.txt_writer import AttDataRepairTxtWriter
from utilities.att_data_repair.models import UniqueCodeCollisionError


class FixedClock:
    def __init__(self, value: datetime = datetime(2026, 8, 3, 9, 0, 0)) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class CodeProvider:
    def __init__(self, *values: int) -> None:
        self.values = list(values)
        self.last = values[-1] if values else 4837

    def __call__(self) -> int:
        if self.values:
            return self.values.pop(0)
        return self.last


def _default_valid(**overrides):
    row = {
        "No": 1,
        "Source_File": "revision.xlsx",
        "Relative_Path": "nested/revision.xlsx",
        "Source_Row": 2,
        "Workflow": "HO",
        "NIK": "000001234",
        "Date_In": "08/03/2026",
        "Time_In": "09:30",
        "Date_Out": "08/03/2026",
        "Time_Out": "17:00",
        "Output_TXT": "Outlook_Revisi_HO_001.txt",
        "Status": "VALID",
    }
    row.update(overrides)
    return row


def _write_report(path: Path, *, valid_rows=(), invalid_rows=()) -> None:
    workbook = Workbook()
    workbook.active.title = "Valid_Records"
    valid = workbook["Valid_Records"]
    invalid = workbook.create_sheet("Invalid_Records")
    valid.append(VALID_RECORDS_COLUMNS)
    invalid.append(INVALID_RECORDS_COLUMNS)
    for item in valid_rows:
        valid.append([item.get(column) for column in VALID_RECORDS_COLUMNS])
    for item in invalid_rows:
        invalid.append([item.get(column) for column in INVALID_RECORDS_COLUMNS])
    workbook.save(path)
    workbook.close()


def _request(path: Path) -> AttDataRepairRequest:
    return AttDataRepairRequest(path, date(2026, 8, 1), date(2026, 8, 31))


def _record(
    record_id: str,
    *,
    workflow: str = "HO",
    nik: str = "000001234",
    in_time: time = time(9, 30),
    out_time: time = time(17, 0),
) -> FinalRecord:
    return FinalRecord(
        record_id=record_id,
        workflow=workflow,
        nik=nik,
        date_in=date(2026, 8, 3),
        time_in=in_time,
        date_out=date(2026, 8, 3),
        time_out=out_time,
        duration_minutes=450,
        source_sheet="Valid_Records",
        source_file="source.xlsx",
        source_row=2,
        final_status="VALID_UNCHANGED",
    )


def test_job_folder_sequence_and_structure(tmp_path: Path) -> None:
    feature = tmp_path / "Utilities" / "Att_Data_Repair"
    (feature / "invalid-folder").mkdir(parents=True)
    (feature / "2026-08-03_01").mkdir()
    (feature / "2026-08-03_99").mkdir()

    paths = AttDataRepairJobManager(FixedClock()).reserve(tmp_path)

    assert paths.job_id == "2026-08-03_100"
    assert paths.job_folder == (
        tmp_path
        / "Utilities"
        / "Att_Data_Repair"
        / "2026-08"
        / "2026-08-03_100"
    )
    assert paths.txt_folder.is_dir()
    assert paths.report_folder.is_dir()
    assert not (paths.job_folder / "Original").exists()


def test_job_folder_collision_tries_next_sequence(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "Utilities" / "Att_Data_Repair" / "2026-08" / "2026-08-03_01").mkdir(
        parents=True
    )
    manager = AttDataRepairJobManager(FixedClock())
    monkeypatch.setattr(manager, "_next_sequence", lambda _root, _date: 1)

    paths = manager.reserve(tmp_path)

    assert paths.job_id == "2026-08-03_02"
    assert paths.job_folder.parent.name == "2026-08"


def test_txt_naming_unique_code_collision_and_retry(tmp_path: Path) -> None:
    txt = tmp_path / "TXT"
    txt.mkdir()
    (txt / "Att_Data_Repair_HO-001_4837.txt").write_text("existing", encoding="utf-8")
    writer = AttDataRepairTxtWriter(CodeProvider(4837, 5837))

    result = writer.write((_record("ADR-1"),), txt)

    assert result.unique_code == 5837
    assert result.artifacts[0].file_name == "Att_Data_Repair_HO-001_5837.txt"
    assert (txt / "Att_Data_Repair_HO-001_4837.txt").read_text(
        encoding="utf-8"
    ) == "existing"


def test_txt_unique_code_retry_exhaustion_raises(tmp_path: Path) -> None:
    txt = tmp_path / "TXT"
    txt.mkdir()
    (txt / "Att_Data_Repair_HO-001_4837.txt").write_text("existing", encoding="utf-8")
    writer = AttDataRepairTxtWriter(CodeProvider(4837), retry_limit=2)

    with pytest.raises(UniqueCodeCollisionError):
        writer.write((_record("ADR-1"),), txt)


def test_txt_format_workflow_split_assignment_and_no_header(tmp_path: Path) -> None:
    writer = AttDataRepairTxtWriter(CodeProvider(4837))
    records = (
        _record("ADR-1", workflow="HO", nik="000001234"),
        _record("ADR-2", workflow="Branch", nik="000000777"),
        _record("ADR-3", workflow="HO", nik="000001234"),
    )

    result = writer.write(records, tmp_path, max_rows_per_file=10_000)

    names = [artifact.file_name for artifact in result.artifacts]
    assert names == [
        "Att_Data_Repair_HO-001_4837.txt",
        "Att_Data_Repair_Branch-001_4837.txt",
    ]
    assert all(artifact.unique_code == 4837 for artifact in result.artifacts)
    ho_text = (tmp_path / names[0]).read_text(encoding="utf-8")
    branch_text = (tmp_path / names[1]).read_text(encoding="utf-8")
    ho_lines = ho_text.splitlines()
    assert ho_lines[0] == (
        '"08/03/2026","000001234","08/03/2026","09:30","08/03/2026","17:00"'
    )
    assert ho_lines[1] == ho_lines[0]
    assert branch_text.splitlines()[0] == (
        '"08/03/2026","000000777","08/03/2026","09:30","08/03/2026","17:00"'
    )
    assert "NIK" not in ho_text
    assert result.record_txt_assignment == {
        "ADR-1": names[0],
        "ADR-2": names[1],
        "ADR-3": names[0],
    }


@pytest.mark.parametrize(
    ("record_count", "expected_files", "expected_rows"),
    [
        (0, 0, []),
        (1, 1, [1]),
        (10_000, 1, [10_000]),
        (10_001, 2, [10_000, 1]),
        (20_001, 3, [10_000, 10_000, 1]),
    ],
)
def test_txt_split_limits_preserve_counts_and_order(
    tmp_path: Path,
    record_count: int,
    expected_files: int,
    expected_rows: list[int],
) -> None:
    records = tuple(_record(f"ADR-{index:05d}") for index in range(record_count))
    result = AttDataRepairTxtWriter(CodeProvider(4837)).write(
        records,
        tmp_path,
        max_rows_per_file=10_000,
    )

    assert len(result.artifacts) == expected_files
    assert [artifact.row_count for artifact in result.artifacts] == expected_rows
    assert sum(artifact.row_count for artifact in result.artifacts) == record_count
    if record_count:
        written = []
        for artifact in result.artifacts:
            written.extend(artifact.record_ids)
        assert written == [record.record_id for record in records]
        assert len(set(written)) == record_count


def test_txt_write_failure_cleans_temporary_file(tmp_path: Path) -> None:
    broken = _record("ADR-1")
    object.__setattr__(broken, "date_in", object())

    with pytest.raises(Exception):
        AttDataRepairTxtWriter(CodeProvider(4837)).write((broken,), tmp_path)

    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob("*.txt"))


def test_run_job_end_to_end_partial_success_outputs_log_and_summary(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.xlsx"
    _write_report(
        source,
        valid_rows=(
            _default_valid(Workflow="HO", NIK="000001234"),
            _default_valid(
                No=2,
                Workflow="Branch",
                NIK="000000777",
                Time_In="7;20",
                Time_Out="7.40",
            ),
            _default_valid(No=3, Workflow="Branch", NIK="#REF!"),
        ),
    )
    before = source.read_bytes()
    engine = AttDataRepairEngine(
        txt_writer=AttDataRepairTxtWriter(CodeProvider(4837)),
        clock=FixedClock(),
    )

    result = engine.run_job(AttDataRepairJobRequest(_request(source), tmp_path))

    assert source.read_bytes() == before
    assert result.status == JobStatus.PARTIAL_SUCCESS
    assert result.paths.job_id == "2026-08-03_01"
    assert result.paths.txt_folder.is_dir()
    assert result.paths.report_folder.is_dir()
    assert not (result.paths.job_folder / "Original").exists()
    assert sorted(path.name for path in result.paths.txt_folder.glob("*.txt")) == [
        "Att_Data_Repair_Branch-001_4837.txt",
        "Att_Data_Repair_HO-001_4837.txt",
    ]
    assert not list(result.paths.txt_folder.glob("*.tmp"))
    assert not (result.paths.job_folder / "summary.json.tmp").exists()
    assert result.record_txt_assignment == {
        "ADR-000001": "Att_Data_Repair_HO-001_4837.txt",
        "ADR-000002": "Att_Data_Repair_Branch-001_4837.txt",
    }

    log = result.paths.process_log.read_text(encoding="utf-8")
    assert "2026-08-03 09:00:00 | INFO | Job ID: 2026-08-03_01" in log
    assert "Source report:" in log
    assert "Analysis counts: final=2; changed=1; anomaly=1" in log
    assert "TXT generated: Att_Data_Repair_HO-001_4837.txt; rows=1" in log
    assert "Job status: PARTIAL_SUCCESS" in log
    assert "Job completed." in log
    assert "ADR-000001" not in log

    summary = json.loads(result.paths.summary_json.read_text(encoding="utf-8"))
    assert summary["schema_version"] == 1
    assert summary["module"] == "Att Data Repair"
    assert summary["engine_version"] == "1.0.0"
    assert summary["status"] == "PARTIAL_SUCCESS"
    assert summary["duration_seconds"] == 0.0
    assert summary["duration_minutes"] == 0.0
    assert summary["counts"]["final_total"] == 2
    assert summary["counts"]["changed_total"] == 1
    assert summary["counts"]["anomaly_total"] == 1
    assert summary["counts"]["workflow"] == {"HO": 1, "Branch": 1}
    assert summary["txt"]["generated"] is True
    assert summary["txt"]["unique_code"] == 4837
    assert summary["report"]["generated"] is True
    assert summary["report"]["file_name"] == (
        "Att_Data_Repair_Report_2026-08-03_01.xlsx"
    )
    assert summary["report"]["sheet_count"] == 8


def test_run_job_success_and_no_valid_records_statuses(tmp_path: Path) -> None:
    success_source = tmp_path / "success.xlsx"
    no_valid_source = tmp_path / "no-valid.xlsx"
    _write_report(success_source, valid_rows=(_default_valid(),))
    _write_report(no_valid_source, valid_rows=(_default_valid(NIK="#N/A"),))
    engine = AttDataRepairEngine(
        txt_writer=AttDataRepairTxtWriter(CodeProvider(4837)),
        clock=FixedClock(),
    )

    success = engine.run_job(AttDataRepairJobRequest(_request(success_source), tmp_path))
    no_valid = engine.run_job(
        AttDataRepairJobRequest(_request(no_valid_source), tmp_path)
    )

    assert success.status == JobStatus.SUCCESS
    assert success.job_id == "2026-08-03_01"
    assert len(tuple(success.paths.txt_folder.glob("*.txt"))) == 1
    assert no_valid.status == JobStatus.NO_VALID_RECORDS
    assert no_valid.job_id == "2026-08-03_02"
    assert not list(no_valid.paths.txt_folder.glob("*.txt"))
    summary = json.loads(no_valid.paths.summary_json.read_text(encoding="utf-8"))
    assert summary["txt"]["generated"] is False
    assert summary["txt"]["file_count"] == 0
    assert summary["txt"]["files"] == []
    assert summary["report"]["generated"] is True


def test_run_job_failed_after_job_folder_writes_failed_summary(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.xlsx"
    _write_report(source, valid_rows=(_default_valid(),))
    writer = AttDataRepairTxtWriter(CodeProvider(999))
    engine = AttDataRepairEngine(txt_writer=writer, clock=FixedClock())

    result = engine.run_job(AttDataRepairJobRequest(_request(source), tmp_path))

    assert result.status == JobStatus.FAILED
    assert result.error_message
    summary = json.loads(result.paths.summary_json.read_text(encoding="utf-8"))
    assert summary["status"] == "FAILED"
    assert "UniqueCodeCollisionError" in summary["error"]
    assert result.paths.process_log.is_file()
