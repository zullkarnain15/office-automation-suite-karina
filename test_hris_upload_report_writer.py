"""
Temporary test file for Sprint 6.10 HRIS Upload Report Writer.

Run from project root:
py test_hris_upload_report_writer.py
"""

from __future__ import annotations

from pathlib import Path

from hris.artifact_writer import HRISJobArtifactWriter
from hris.job_manager import HRISUploadJobManager
from hris.report_writer import HRISUploadReportWriter
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
    Create sample TXT files for upload report writer test.
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
    print("OAS-K Sprint 6.10 HRIS Upload Report Writer Test")
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

    report_writer = HRISUploadReportWriter()

    report_file = report_writer.write_upload_report(
        artifacts=artifacts,
        upload_plan=upload_plan,
    )

    artifact_writer.write_process_log(
        artifacts=artifacts,
        message=f"Upload report created: {report_file.name}",
    )

    print("REPORT SUMMARY")
    print("-" * 80)
    print(f"Job ID              : {artifacts.job_id}")
    print(f"Workflow            : {artifacts.workflow}")
    print(f"Job Report Folder   : {artifacts.job_report_folder}")
    print(f"Report File         : {report_file}")
    print(f"Report Exists       : {report_file.exists()}")
    print(f"Process Log Exists  : {artifacts.process_log_file.exists()}")
    print(f"Summary JSON Exists : {artifacts.summary_json_file.exists()}")

    print()
    print("EXPECTED REPORT")
    print("-" * 80)
    print(f"Upload_Report_{WORKFLOW}.xlsx")

    print()
    print("=" * 80)
    print("HRIS Upload Report Writer test finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()
