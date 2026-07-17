from pathlib import Path
from types import SimpleNamespace

from hris.diagnostics import HRISDiagnosticPackWriter


def test_diagnostic_redaction_preserves_nested_step_structure() -> None:
    writer = HRISDiagnosticPackWriter()

    result = writer._redact_mapping(
        {
            "assisted_steps": [
                {
                    "step_name": "upload",
                    "action": "click",
                }
            ],
            "nested": {
                "status": "SUBMITTED",
                "access_token": "secret-value",
            },
        }
    )

    assert result["assisted_steps"] == [
        {
            "step_name": "upload",
            "action": "click",
        }
    ]
    assert result["nested"]["status"] == "SUBMITTED"
    assert result["nested"]["access_token"] == "<REDACTED>"


def test_diagnostic_folder_and_zip_are_unique_per_job(tmp_path: Path) -> None:
    job_id = "HRIS_HO_20260716_153045"
    report_folder = tmp_path / "HRIS" / "HO" / "Report" / "2026-07"
    report_folder.mkdir(parents=True)
    process_log = report_folder / f"Upload_Process_{job_id}.txt"
    summary_json = report_folder / f"Upload_Summary_{job_id}.json"
    process_log.write_text("log", encoding="utf-8")
    summary_json.write_text("{}", encoding="utf-8")
    artifacts = SimpleNamespace(
        job_id=job_id,
        workflow="HO",
        job_report_folder=report_folder,
        process_log_file=process_log,
        summary_json_file=summary_json,
    )

    diagnostic_folder = HRISDiagnosticPackWriter().write_diagnostic_pack(
        artifacts=artifacts,
        configuration=None,
        upload_plan=None,
        report_file=None,
        page=None,
        error_message="Synthetic failure",
        traceback_text="Synthetic traceback",
        stage="test",
    )

    assert diagnostic_folder == report_folder / f"Diagnostic_{job_id}"
    assert diagnostic_folder.is_dir()
    assert diagnostic_folder.with_suffix(".zip").is_file()
    assert not (report_folder / "Diagnostic.zip").exists()
