"""
Temporary test file for Sprint 6.8 HRIS Upload Job Manager.

Run from project root:
py test_hris_upload_job_manager.py
"""

from __future__ import annotations

from pathlib import Path

from hris.job_manager import HRISUploadJobManager
from shared.config_manager import HRISConfigurationReader


CONFIG_FILE = Path(
    r"D:\Python Project\OfficeAutomationSuite-Karina\config\hris\OAS-K_HRIS_Configuration.xlsx"
)

SAMPLE_TXT_FOLDER = Path(
    r"D:\Python Project\OfficeAutomationSuite-Karina\temp\hris_txt_sample"
)

WORKFLOW = "HO"


def prepare_sample_txt_files() -> None:
    """
    Create sample TXT files for upload plan test.

    This does not represent real HRIS content.
    It only tests file scanning and Run Control assignment.
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
    print("OAS-K Sprint 6.8 HRIS Upload Job Manager Test")
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

    print("PRE-VALIDATION SUMMARY")
    print("-" * 80)
    print(f"Workflow              : {upload_plan.workflow}")
    print(f"TXT folder            : {upload_plan.txt_folder}")
    print(f"TXT files found       : {upload_plan.total_txt_files}")
    print(f"Run Control available : {upload_plan.total_run_controls}")
    print(f"Is valid              : {upload_plan.is_valid}")
    print(f"Message               : {upload_plan.message}")

    print()
    print("UPLOAD PLAN")
    print("-" * 80)

    if upload_plan.plan_items:
        for item in upload_plan.plan_items:
            print(
                f"{item.sequence}. "
                f"{item.txt_file_name} -> "
                f"Run Control {item.run_control_id} "
                f"({item.status})"
            )
    else:
        print("(No upload plan item)")

    print()
    print("JOB ID SAMPLE")
    print("-" * 80)
    print(job_manager.create_job_id(WORKFLOW))

    print()
    print("=" * 80)
    print("HRIS Upload Job Manager test finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()
