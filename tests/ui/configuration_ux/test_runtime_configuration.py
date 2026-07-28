from __future__ import annotations

from pathlib import Path

from shared.config_manager import (
    AttendanceConfigurationReader,
    OutlookRevisiConfigurationReader,
)
from ui.adapters.attendance_adapter import AttendanceAdapter
from ui.adapters.outlook_revisi_adapter import OutlookRevisiAdapter
from ui.attendance_models import AttendanceResolvedRequest
from ui.outlook_revisi_models import OutlookRevisiResolvedRequest
from tests.ui.module_configuration.test_module_configuration_service import (
    configured_database,
)


def test_attendance_sqlite_exports_temporary_legacy_workbook(tmp_path: Path) -> None:
    database = configured_database(tmp_path)
    request = AttendanceResolvedRequest(
        job_id="UI5B-A",
        database_path=database,
        configuration_path=None,
        workflow="HO",
        output_root=tmp_path / "output",
        period_start="2026-07-01",
        period_end="2026-07-31",
        used_global_output=True,
        used_global_period=True,
        generate_txt=True,
        generate_report=True,
    )
    with AttendanceAdapter._configuration_path(request) as path:
        assert path.is_file() and tmp_path not in path.parents
        configuration = AttendanceConfigurationReader(path).read()
        assert configuration.ho_mdb_list[0].code == "HO1"
        temporary = path
    assert not temporary.exists()


def test_outlook_sqlite_exports_temporary_legacy_workbook(tmp_path: Path) -> None:
    database = configured_database(tmp_path)
    request = OutlookRevisiResolvedRequest(
        job_id="UI5B-O",
        database_path=database,
        configuration_path=None,
        workflow="HO",
        output_root=tmp_path / "output",
        period_start="2026-07-01",
        period_end="2026-07-31",
        payroll_period="07-2026",
        used_global_output=True,
        used_global_period=True,
        dry_run=True,
        message_limit=5,
    )
    with OutlookRevisiAdapter._configuration_path(request) as path:
        assert path.is_file() and tmp_path not in path.parents
        configuration = OutlookRevisiConfigurationReader(path).read()
        assert configuration.general["Mailbox_SMTP"] == "karina.hr.1@oto.co.id"
        assert configuration.reply_templates[0].body_template == "Line 1\nLine 2"
        temporary = path
    assert not temporary.exists()
