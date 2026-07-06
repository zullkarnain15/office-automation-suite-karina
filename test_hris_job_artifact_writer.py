"""
Temporary test file for Sprint 6.9 HRIS Job Artifact Writer.

Run from project root:
py test_hris_job_artifact_writer.py
"""

from __future__ import annotations

from pathlib import Path

from hris.artifact_writer import HRISJobArtifactWriter
from hris.job_manager import HRISUploadJobManager
from shared.config_manager import HRISConfigurationReader


CONFIG_FILE = Path(
    r"D:\Python Project\OfficeAutomationSuite-Karina\config\hris\OAS-K_HRIS_Configuration.xlsx"
)

SAMPLE_TXT_FOLDER = Path(
    r"D:\Python Project\OfficeAutomationSuite-Karina\temp\hris_txt_sample"
)

OUTPUT_ROOT = Path(
    r"D:\Python Project\OfficeAutomationSuite-Karina\output"
)

WORKFLOW = "HO"


def prepare_sample_txt_files() -> None:
    """
    Create sample TXT files for artifact writer test.
    """
    SAMPLE_TXT_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    sample_files = [
        "Attendance_HO_001.txt",
        "Attendance_HO_002.txt",
        "Attendance_HO_003.txt",
    ]

    for file_name in sample_files:
        file_path = SAMPLE_TXT_FOLDER / file_name

        if not file_path.exists():
            file_path.write_text(
                '"03/30/2026","100808219","03/30/2026","13:20","03/30/2026","16:39"\n',
                encoding="utf-8",
            )


def main() -> None:
    print("=" * 80)
    print("OAS-K Sprint 6.9 HRIS Job Artifact Writer Test")
    print("=" * 80)

    prepare_sample_txt_files()

    reader = HRISConfigurationReader(CONFIG_FILE)
    configuration = reader.read()

    job_manager = HRISUploadJobManager()

    upload_plan = job_manager.create_upload_plan(
        configuration=configuration,
        txt_folder=SAMPLE_TXT_FOLDER,
        workflow=WORKFLOW,
    )

    if not upload_plan.is_valid:
        print("Upload plan is invalid.")
        print(upload_plan.message)
        return

    job_id = job_manager.create_job_id(WORKFLOW)

    artifact_writer = HRISJobArtifactWriter()

    artifacts = artifact_writer.prepare_job_artifacts(
        output_root=OUTPUT_ROOT,
        workflow=WORKFLOW,
        job_id=job_id,
        upload_plan=upload_plan,
    )

    artifact_writer.write_process_log(
        artifacts=artifacts,
        message="Pre-validation passed.",
    )

    artifact_writer.write_process_log(
        artifacts=artifacts,
        message=f"Upload plan created. Total item: {len(upload_plan.plan_items)}.",
    )

    summary = artifact_writer.read_summary(
        artifacts.summary_json_file,
    )

    print("ARTIFACT SUMMARY")
    print("-" * 80)
    print(f"Job ID              : {artifacts.job_id}")
    print(f"Workflow            : {artifacts.workflow}")
    print(f"Workflow Root       : {artifacts.workflow_root}")
    print(f"Upload Folder       : {artifacts.upload_folder}")
    print(f"Failed Folder       : {artifacts.failed_folder}")
    print(f"Job Report Folder   : {artifacts.job_report_folder}")
    print(f"Process Log Exists  : {artifacts.process_log_file.exists()}")
    print(f"Summary JSON Exists : {artifacts.summary_json_file.exists()}")

    print()
    print("SUMMARY JSON CHECK")
    print("-" * 80)
    print(f"Status              : {summary.get('status')}")
    print(f"Total Items         : {summary.get('total_items')}")
    print(f"Next Sequence       : {summary.get('next_sequence')}")
    print(f"Plan Item Count     : {len(summary.get('plan_items', []))}")

    print()
    print("PROCESS LOG PREVIEW")
    print("-" * 80)
    print(artifacts.process_log_file.read_text(encoding="utf-8"))

    print("=" * 80)
    print("HRIS Job Artifact Writer test finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()
