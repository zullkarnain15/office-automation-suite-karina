"""Global Settings and module usage facade tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from shared.database import SchemaManager
from ui.services.database_settings_service import DatabaseSettingsService
from ui.services.protocols import (
    GlobalSettingsDraft,
    HRISTxtSourceDraft,
    ModuleGlobalUsage,
    OutlookOperationalSettingsDraft,
)


@pytest.fixture
def settings_database(tmp_path: Path) -> Path:
    path = tmp_path / "settings.db"
    SchemaManager().initialize_database(path, "ui2-test")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO attendance_settings "
            "(attendance_settings_id, updated_at) VALUES (1, '2026-01-01')"
        )
        connection.execute(
            "INSERT INTO comparison_settings "
            "(comparison_settings_id, updated_at) VALUES (1, '2026-01-01')"
        )
        connection.execute(
            """
            INSERT INTO outlook_settings (
                outlook_settings_id, mailbox_smtp, updated_at
            ) VALUES (1, 'karina.hr.1@oto.co.id', '2026-01-01')
            """
        )
        connection.execute(
            "INSERT INTO attachment_consolidation_settings "
            "(attachment_settings_id, updated_at) VALUES (1, '2026-01-01')"
        )
    return path


def test_global_settings_load_empty(settings_database: Path) -> None:
    assert DatabaseSettingsService().load_global_settings(
        settings_database
    ) == GlobalSettingsDraft()


def test_global_settings_save_and_load(settings_database: Path) -> None:
    service = DatabaseSettingsService()
    draft = GlobalSettingsDraft("D:/Output", "2026-01-01", "2026-01-31")
    assert service.save_global_settings(settings_database, draft) == draft
    assert service.load_global_settings(settings_database) == draft


def test_hris_txt_sources_are_local_preferences_and_allow_empty_values(
    settings_database: Path,
    tmp_path: Path,
) -> None:
    service = DatabaseSettingsService()
    ho = tmp_path / "HRIS HO"
    branch = tmp_path / "HRIS Branch"
    ho.mkdir()
    branch.mkdir()
    draft = HRISTxtSourceDraft(str(ho), str(branch))

    assert service.save_hris_txt_source_preferences(settings_database, draft) == draft
    assert service.load_hris_txt_source_preferences(settings_database) == draft
    assert service.save_hris_txt_source_preferences(
        settings_database, HRISTxtSourceDraft()
    ) == HRISTxtSourceDraft()


def test_hris_txt_sources_reject_unavailable_folder(settings_database: Path) -> None:
    with pytest.raises(ValueError, match="HO tidak ditemukan"):
        DatabaseSettingsService().save_hris_txt_source_preferences(
            settings_database,
            HRISTxtSourceDraft("D:/folder-yang-tidak-ada", ""),
        )


def test_invalid_period_is_rejected(settings_database: Path) -> None:
    with pytest.raises(ValueError):
        DatabaseSettingsService().save_global_settings(
            settings_database,
            GlobalSettingsDraft("D:/Output", "2026-02-01", "2026-01-01"),
        )


def test_partial_period_is_rejected(settings_database: Path) -> None:
    with pytest.raises(ValueError):
        DatabaseSettingsService().save_global_settings(
            settings_database,
            GlobalSettingsDraft("D:/Output", "2026-01-01", None),
        )


def test_global_save_records_audit(settings_database: Path) -> None:
    DatabaseSettingsService().save_global_settings(
        settings_database,
        GlobalSettingsDraft("D:/Output"),
        operator="tester",
    )
    with sqlite3.connect(settings_database) as connection:
        rows = connection.execute(
            "SELECT setting_key, change_source FROM configuration_audit"
        ).fetchall()
    assert ("output_root", "Unified UI") in rows


def test_module_usage_load_matches_schema(settings_database: Path) -> None:
    values = DatabaseSettingsService().load_module_global_usage(
        settings_database
    )
    by_module = {value.module: value for value in values}
    assert len(values) == 5
    assert by_module["ATTENDANCE"].use_global_period is True
    assert (
        by_module["ATTACHMENT_CONSOLIDATION"].use_global_period is None
    )
    assert by_module["OUTLOOK_REVISI"].available
    assert by_module["OUTLOOK_REVISI"].use_global_period is None


def test_outlook_operational_settings_save_is_direct_and_audited(
    settings_database: Path,
) -> None:
    service = DatabaseSettingsService()
    draft = OutlookOperationalSettingsDraft(
        "07-2026",
        "Hubungi PIC Attendance.",
    )

    assert (
        service.save_outlook_operational_settings(settings_database, draft)
        == draft
    )
    assert service.load_outlook_operational_settings(settings_database) == draft

    with sqlite3.connect(settings_database) as connection:
        keys = {
            row[0]
            for row in connection.execute(
                """
                SELECT setting_key
                FROM configuration_audit
                WHERE module_code = 'OUTLOOK_REVISI'
                """
            )
        }
    assert keys == {"payroll_period", "resubmit_deadline"}


def test_outlook_operational_settings_reject_invalid_period(
    settings_database: Path,
) -> None:
    with pytest.raises(ValueError, match="MM-YYYY"):
        DatabaseSettingsService().save_outlook_operational_settings(
            settings_database,
            OutlookOperationalSettingsDraft("7/2026", ""),
        )


def test_module_usage_save(settings_database: Path) -> None:
    service = DatabaseSettingsService()
    values = (
        ModuleGlobalUsage("ATTENDANCE", "Attendance", False, False, True),
        ModuleGlobalUsage(
            "ATTACHMENT_CONSOLIDATION",
            "Attachment Consolidation",
            False,
            None,
            True,
        ),
    )
    result = service.save_module_global_usage(settings_database, values)
    by_module = {value.module: value for value in result}
    assert not by_module["ATTENDANCE"].use_global_output
    assert not by_module["ATTENDANCE"].use_global_period
    assert not by_module["ATTACHMENT_CONSOLIDATION"].use_global_output


def test_module_usage_save_is_audited(settings_database: Path) -> None:
    DatabaseSettingsService().save_module_global_usage(
        settings_database,
        (ModuleGlobalUsage("ATTENDANCE", "Attendance", False, True, True),),
    )
    with sqlite3.connect(settings_database) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM configuration_audit "
            "WHERE module_code='ATTENDANCE'"
        ).fetchone()[0]
    assert count == 1


def test_database_validation_is_structured(settings_database: Path) -> None:
    result = DatabaseSettingsService().validate_database(settings_database)
    assert result.is_valid
    assert result.integrity_ok
    assert result.foreign_keys_ok
