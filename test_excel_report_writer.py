"""
Temporary test file for Sprint 5.7 Excel Report Writer.

Run from project root:
python test_excel_report_writer.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from attendance.engine import AttendanceExcelReportWriter
from attendance.engine import AttendanceHRISTXTWriter
from attendance.engine import AttendancePairingEngine
from attendance.engine import AttendanceValidationEngine
from attendance.extractor import AttendanceMDBExtractor
from config.app_config import DATE_FORMAT


MDB_PATH = Path(
    r"D:\Python Project\Attendance Configuration\mdb\HO\newatt2000.mdb"
)

OUTPUT_ROOT = Path(
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
    print("OAS-K Excel Report Writer Test")
    print("=" * 80)

    with AttendanceMDBExtractor(MDB_PATH) as extractor:
        raw_logs = extractor.fetch_raw_logs(
            date_from=date_from,
            date_to=date_to,
        )

    pairing_engine = AttendancePairingEngine()
    paired_records = pairing_engine.pair_raw_logs(raw_logs)

    validation_engine = AttendanceValidationEngine()
    validation_result = validation_engine.validate_paired_records(
        paired_records
    )

    valid_records = validation_result["valid_records"]
    anomaly_records = validation_result["anomaly_records"]
    all_records = validation_result["all_records"]
    validation_summary = validation_result["summary"]

    txt_writer = AttendanceHRISTXTWriter()

    txt_result = txt_writer.write_txt_files(
        valid_records=valid_records,
        output_root=OUTPUT_ROOT,
        workflow=WORKFLOW,
        max_rows_per_file=10000,
    )

    report_writer = AttendanceExcelReportWriter()

    report_result = report_writer.write_report(
        all_records=all_records,
        valid_records=valid_records,
        anomaly_records=anomaly_records,
        validation_summary=validation_summary,
        output_root=OUTPUT_ROOT,
        workflow=WORKFLOW,
        job_id=txt_result["job_id"],
    )

    print("REPORT WRITER SUMMARY")
    print("-" * 80)
    print(f"Raw log count       : {len(raw_logs)}")
    print(f"Pair result count   : {len(paired_records)}")
    print(f"Valid TXT records   : {len(valid_records)}")
    print(f"Anomaly records     : {len(anomaly_records)}")
    print(f"Job ID              : {report_result['job_id']}")
    print(f"Report folder       : {report_result['report_folder']}")
    print(f"Report file         : {report_result['report_file']}")
    print(f"Sheet count         : {report_result['sheet_count']}")

    print()
    print("=" * 80)
    print("Excel report writer test finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()