"""
Temporary test file for Sprint 6.11 HRIS Upload Engine.

Run from project root:
py test_hris_upload_engine.py
"""

from __future__ import annotations

from pathlib import Path

from hris.engine import HRISUploadEngine


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
    Create sample TXT files for HRIS upload engine test.
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
    print("OAS-K Sprint 6.11 HRIS Upload Engine Test")
    print("=" * 80)

    prepare_sample_txt_files()

    engine = HRISUploadEngine(
        configuration_file=CONFIG_FILE,
        txt_folder=SAMPLE_TXT_FOLDER,
        output_root=OUTPUT_ROOT,
        workflow=WORKFLOW,
    )

    result = engine.prepare_upload_job()

    print("ENGINE RESULT")
    print("-" * 80)
    print(f"Success             : {result.success}")
    print(f"Message             : {result.message}")
    print(f"Job ID              : {result.job_id}")
    print(f"Workflow            : {result.workflow}")

    if result.upload_plan:
        print(f"TXT files found     : {result.upload_plan.total_txt_files}")
        print(f"Run Control count   : {result.upload_plan.total_run_controls}")
        print(f"Plan item count     : {len(result.upload_plan.plan_items)}")

    if result.artifacts:
        print(f"Job Report Folder   : {result.artifacts.job_report_folder}")
        print(f"Process Log Exists  : {result.artifacts.process_log_file.exists()}")
        print(f"Summary JSON Exists : {result.artifacts.summary_json_file.exists()}")

    if result.report_file:
        print(f"Report File         : {result.report_file}")
        print(f"Report Exists       : {result.report_file.exists()}")

    print()
    print("=" * 80)
    print("HRIS Upload Engine test finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()