from datetime import datetime
from pathlib import Path
import re

from attendance.engine import AttendanceExcelReportWriter
from attendance.engine import AttendanceHRISTXTWriter
from attendance.engine import AttendanceRunArtifactWriter


def test_txt_output_uses_attendance_folder_and_time_suffix(tmp_path: Path) -> None:
    writer = AttendanceHRISTXTWriter()
    result = writer.write_txt_files(
        valid_records=[
            {
                "attendance_date": "2026-07-10",
                "nik": "123456789",
                "source_mdb": "HO",
                "check_in": datetime(2026, 7, 10, 8, 0),
                "check_out": datetime(2026, 7, 10, 17, 0),
            }
        ],
        output_root=tmp_path,
        workflow="HO",
        max_rows_per_file=10000,
        job_id="20260710_153045",
    )

    output_folder = Path(result["output_folder"])
    generated_file = Path(result["generated_files"][0]["file_path"])

    assert output_folder == (
        tmp_path
        / "Attendance"
        / "HO"
        / "2026-07"
        / "20260710_153045"
        / "TXT"
    )
    assert re.fullmatch(
        r"Attendance_HO_001_153045_\d{3}\.txt",
        generated_file.name,
    )
    assert generated_file.exists()


def test_txt_random_suffix_is_unique_with_collision_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    random_values = iter((7, 7, 42))
    monkeypatch.setattr(
        "attendance.engine.secrets.randbelow",
        lambda _limit: next(random_values),
    )
    records = [
        {
            "attendance_date": "2026-07-10",
            "nik": f"{index:09d}",
            "source_mdb": "HO",
            "check_in": datetime(2026, 7, 10, 8, 0),
            "check_out": datetime(2026, 7, 10, 17, 0),
        }
        for index in range(2)
    ]

    result = AttendanceHRISTXTWriter().write_txt_files(
        valid_records=records,
        output_root=tmp_path,
        workflow="HO",
        max_rows_per_file=1,
        job_id="20260710_153045",
    )

    assert [
        Path(item["file_path"]).name
        for item in result["generated_files"]
    ] == [
        "Attendance_HO_001_153045_007.txt",
        "Attendance_HO_002_153045_042.txt",
    ]


def test_report_output_uses_attendance_folder_and_time_suffix(tmp_path: Path) -> None:
    writer = AttendanceExcelReportWriter()
    result = writer.write_report(
        all_records=[],
        valid_records=[],
        anomaly_records=[],
        validation_summary={},
        output_root=tmp_path,
        workflow="Branch",
        job_id="20260710_153045",
    )

    report_folder = Path(result["report_folder"])
    report_file = Path(result["report_file"])

    assert report_folder == (
        tmp_path
        / "Attendance"
        / "Branch"
        / "2026-07"
        / "20260710_153045"
        / "Report"
    )
    assert report_file.name == "Export_Attendance_Branch_153045.xlsx"
    assert report_file.exists()


def test_artifacts_are_written_in_attendance_run_folder(tmp_path: Path) -> None:
    writer = AttendanceRunArtifactWriter()
    result = writer.write_artifacts(
        result={
            "job_id": "20260710_153045",
            "workflow": "HO",
            "date_from": datetime(2026, 7, 1),
            "date_to": datetime(2026, 7, 10),
            "mdb_summary": [],
            "validation_summary": {},
            "txt_result": None,
            "report_result": None,
        },
        output_root=tmp_path,
        workflow="HO",
        job_id="20260710_153045",
    )

    artifact_folder = Path(result["artifact_folder"])

    assert artifact_folder == (
        tmp_path
        / "Attendance"
        / "HO"
        / "2026-07"
        / "20260710_153045"
    )
    assert Path(result["process_log"]).name == "Process.log"
    assert Path(result["summary_json"]).name == "summary.json"
    assert Path(result["process_log"]).exists()
    assert Path(result["summary_json"]).exists()
