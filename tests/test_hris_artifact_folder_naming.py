from pathlib import Path
from types import SimpleNamespace

from hris.artifact_writer import HRISJobArtifactWriter


def test_hris_ho_job_folder_uses_timestamp_only() -> None:
    assert HRISJobArtifactWriter._job_folder_name(
        "HRIS_HO_20260706_161042"
    ) == "20260706_161042"


def test_hris_branch_job_folder_uses_timestamp_only() -> None:
    assert HRISJobArtifactWriter._job_folder_name(
        "HRIS_BRANCH_20260706_161042"
    ) == "20260706_161042"


def test_hris_timestamp_job_id_remains_unchanged() -> None:
    assert HRISJobArtifactWriter._job_folder_name(
        "20260706_161042"
    ) == "20260706_161042"


def test_hris_month_folder_is_derived_from_job_id() -> None:
    assert HRISJobArtifactWriter._month_folder_name(
        "HRIS_HO_20260706_161042"
    ) == "2026-07"


def test_hris_artifacts_use_type_then_month_without_job_folder(
    tmp_path: Path,
) -> None:
    upload_plan = SimpleNamespace(
        txt_folder=tmp_path / "TXT",
        total_txt_files=0,
        total_run_controls=0,
        plan_items=[],
        message="Ready",
    )

    artifacts = HRISJobArtifactWriter().prepare_job_artifacts(
        output_root=tmp_path,
        workflow="HO",
        job_id="HRIS_HO_20260716_153045",
        upload_plan=upload_plan,
    )

    workflow_root = tmp_path / "HRIS" / "HO"
    assert artifacts.upload_folder == workflow_root / "Upload" / "2026-07"
    assert artifacts.failed_folder == workflow_root / "Failed" / "2026-07"
    assert artifacts.report_root == workflow_root / "Report"
    assert artifacts.job_report_folder == (
        workflow_root / "Report" / "2026-07"
    )
    assert artifacts.process_log_file.parent == artifacts.job_report_folder
    assert artifacts.summary_json_file.parent == artifacts.job_report_folder
    assert artifacts.process_log_file.exists()
    assert artifacts.summary_json_file.exists()
    assert not (artifacts.job_report_folder / "20260716_153045").exists()
