from __future__ import annotations

from pathlib import Path

from shared.database.importing.models import (
    ChangeOperation,
    ConfigImportChange,
    ConfigImportIssue,
    ConfigImportPreview,
    IssueSeverity,
)
from ui.configuration_ux_models import ConfigurationModuleStatus
from ui.services.configuration_ui_service import ConfigurationUIService


def _preview(tmp_path: Path) -> ConfigImportPreview:
    return ConfigImportPreview(
        source_files=(tmp_path / "Unified.xlsx",),
        detected_workbooks=(),
        modules=("GLOBAL", "OUTLOOK_REVISI"),
        valid_count=2,
        warning_count=1,
        error_count=0,
        critical_count=0,
        confirmation_required=True,
        can_commit=True,
        changes=(
            ConfigImportChange("GLOBAL", "global_settings", "output_root", ChangeOperation.UPDATE, "old", "new", False),
            ConfigImportChange("OUTLOOK_REVISI", "outlook_subject_rules", "rule", ChangeOperation.INSERT, None, "new", False),
            ConfigImportChange("OUTLOOK_REVISI", "outlook_subject_rules", "old-rule", ChangeOperation.DELETE, "old", None, True),
        ),
        issues=(
            ConfigImportIssue(
                "OUTLOOK_AUTOMATIC_SEND_ENABLED",
                IssueSeverity.WARNING,
                "OUTLOOK_REVISI",
                "technical fallback",
                confirmation_required=True,
            ),
        ),
        generated_at="2026-07-21",
        database_snapshot_hash="fixture",
    )


def test_preview_is_translated_to_user_friendly_summary(tmp_path: Path) -> None:
    summary = ConfigurationUIService.present_preview(_preview(tmp_path))
    assert dict(summary.modules) == {
        "GLOBAL": ConfigurationModuleStatus.READY,
        "OUTLOOK_REVISI": ConfigurationModuleStatus.ATTENTION,
    }
    assert (summary.insert_count, summary.update_count, summary.delete_count) == (1, 1, 1)
    assert summary.issues[0].title == "Pengiriman email otomatis aktif."
    assert summary.issues[0].technical_code == "OUTLOOK_AUTOMATIC_SEND_ENABLED"


def test_outlook_sender_issue_shows_excel_location() -> None:
    issue = ConfigImportIssue(
        code="ACTIVE_SENDER_EMAIL_MISSING",
        severity=IssueSeverity.ERROR,
        module="OUTLOOK_REVISI",
        message="Active sender row has no email address.",
        sheet="Outlook_HO_Senders",
        row_number=1323,
        field="sender_email",
    )

    presented = ConfigurationUIService._present_issue(issue)

    assert presented.title == "Email pengirim Outlook aktif masih kosong."
    assert "sheet Outlook_HO_Senders" in presented.detail
    assert "baris 1323" in presented.detail
    assert "kolom sender_email" in presented.detail


def test_primary_ui_terminology_hides_internal_action_names() -> None:
    source = Path("ui/pages/settings/configuration_section.py").read_text(encoding="utf-8")
    assert "Pilih File Excel" in source
    assert "Periksa Konfigurasi" in source
    assert "Terapkan Konfigurasi" in source
    assert "Build Import Preview" not in source
    assert "Commit Preview Modules" not in source
    assert "Resolve Global Conflict" not in source


def test_module_selector_is_advanced_and_hidden_by_default() -> None:
    source = Path("ui/pages/settings/configuration_section.py").read_text(encoding="utf-8")
    assert "self.advanced_frame.grid_remove()" in source
    assert "self.module_frame.grid_remove()" in source
