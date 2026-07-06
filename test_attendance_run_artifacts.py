"""
Temporary test file for Sprint 5.11 Run Artifacts.

Run from project root:
py test_attendance_run_artifacts.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from attendance.engine import AttendanceProcessEngine
from config.app_config import DATE_FORMAT
from shared.config_manager import AttendanceConfigurationReader


CONFIG_FILE = Path(
    r"D:\Python Project\Attendance Configuration\config\OAS-K_Attendance_Configuration.xlsx"
)

DEFAULT_OUTPUT_ROOT = Path(
    r"D:\Python Project\Attendance Configuration\output"
)

DATE_FROM = "03/30/2026"
DATE_TO = "03/30/2026"
WORKFLOW = "HO"


def main() -> None:
    date_from = datetime.strptime(
        DATE_FROM,
        DATE_FORMAT,
    )

    date_to = datetime.strptime(
        DATE_TO,
        DATE_FORMAT,
    )

    print("=" * 80)
    print("OAS-K Sprint 5.11 Run Artifacts Test")
    print("=" * 80)

    reader = AttendanceConfigurationReader(CONFIG_FILE)
    configuration = reader.read()
    output_root = (
        configuration.get_output_folder()
        or DEFAULT_OUTPUT_ROOT
    )

    process_engine = AttendanceProcessEngine()

    result = process_engine.run(
        configuration=configuration,
        output_root=output_root,
        workflow=WORKFLOW,
        date_from=date_from,
        date_to=date_to,
        generate_txt=True,
        generate_report=True,
    )

    print("PROCESS SUMMARY")
    print("-" * 80)
    print(f"Job ID              : {result['job_id']}")
    print(f"Workflow            : {result['workflow']}")
    print(f"Raw log count       : {result['raw_log_count']}")
    print(f"Paired record count : {result['paired_record_count']}")
    print(f"Valid record count  : {result['valid_record_count']}")
    print(f"Anomaly count       : {result['anomaly_record_count']}")

    artifact_result = result.get("artifact_result")

    print()
    print("ARTIFACT RESULT")
    print("-" * 80)
    print(artifact_result)

    if artifact_result:
        process_log = Path(artifact_result["process_log"])
        summary_json = Path(artifact_result["summary_json"])

        print()
        print("FILE CHECK")
        print("-" * 80)
        print(f"Process.log exists : {process_log.exists()}")
        print(f"summary.json exists: {summary_json.exists()}")
        print(f"Process.log path   : {process_log}")
        print(f"summary.json path  : {summary_json}")

    print()
    print("=" * 80)
    print("Sprint 5.11 run artifacts test finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()
