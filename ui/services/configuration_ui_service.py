"""DB2 import/export facade for Settings."""

from __future__ import annotations

import shutil
import hashlib
from datetime import datetime
from pathlib import Path

from shared.database.exporting import export_current_configuration
from shared.database.importing import ConfigImportService
from shared.database.importing.models import ConfigImportCommitRequest
from shared.database.importing.models import ImportMode
from shared.database.importing.models import ChangeOperation
from shared.database.importing.workbook_detector import detect_workbook
from ui.configuration_ux_models import (
    ConfigurationImportUserSummary,
    ConfigurationIssuePresentation,
    ConfigurationModuleStatus,
)


class ConfigurationUIService:
    def __init__(
        self,
        template_path: Path,
        importer: ConfigImportService | None = None,
    ) -> None:
        self.template_path = template_path
        self.importer = importer or ConfigImportService()

    def preview(
        self,
        database_path: Path,
        source_files: tuple[Path, ...],
        *,
        global_resolution: dict[str, object] | None = None,
    ):
        return self.importer.preview(
            database_path,
            source_files,
            global_resolution=global_resolution,
        )

    @staticmethod
    def inspect_file(source_file: Path):
        return detect_workbook(source_file)

    @staticmethod
    def present_preview(preview) -> ConfigurationImportUserSummary:
        issues = tuple(
            ConfigurationUIService._present_issue(item)
            for item in preview.issues
        )
        module_values = []
        for module in preview.modules:
            module_issues = tuple(item for item in preview.issues if item.module == module)
            if any(item.severity.value in {"ERROR", "CRITICAL"} for item in module_issues):
                status = ConfigurationModuleStatus.ERROR
            elif module_issues:
                status = ConfigurationModuleStatus.ATTENTION
            else:
                status = ConfigurationModuleStatus.READY
            module_values.append((module, status))
        operations = [item.operation for item in preview.changes]
        return ConfigurationImportUserSummary(
            tuple(module_values),
            operations.count(ChangeOperation.INSERT),
            operations.count(ChangeOperation.UPDATE),
            operations.count(ChangeOperation.DELETE),
            preview.warning_count,
            preview.error_count + preview.critical_count,
            preview.confirmation_required,
            issues,
        )

    @staticmethod
    def _present_issue(item) -> ConfigurationIssuePresentation:
        title, detail = ConfigurationUIService._issue_text(
            item.code,
            item.message,
        )
        location = []
        if item.sheet:
            location.append(f"sheet {item.sheet}")
        if item.row_number is not None:
            location.append(f"baris {item.row_number}")
        if item.field:
            location.append(f"kolom {item.field}")
        if location:
            detail = f"{detail} Lokasi: {', '.join(location)}."
        return ConfigurationIssuePresentation(
            title,
            detail,
            item.severity.value,
            item.code,
        )

    @staticmethod
    def _issue_text(code: str, fallback: str) -> tuple[str, str]:
        mapping = {
            "OUTLOOK_AUTOMATIC_SEND_ENABLED": (
                "Pengiriman email otomatis aktif.",
                "Periksa Send Mode, Auto Reply, dan penerima sebelum menerapkan.",
            ),
            "HRIS_MOCK_URL_DETECTED": (
                "URL HRIS terlihat sebagai alamat pengujian.",
                fallback,
            ),
            "DEVELOPMENT_PATH_DETECTED": (
                "Beberapa path mengarah ke folder pengembangan.",
                fallback,
            ),
            "GLOBAL_OUTPUT_CONFLICT": (
                "Folder Output Global berbeda.",
                "Pilih nilai aktif, nilai dari file, atau folder lain.",
            ),
            "GLOBAL_PERIOD_CONFLICT": (
                "Periode Global berbeda.",
                "Pilih periode aktif, periode dari file, atau nilai lain.",
            ),
            "ACTIVE_SENDER_EMAIL_MISSING": (
                "Email pengirim Outlook aktif masih kosong.",
                "Isi sender_email atau nonaktifkan baris tersebut, lalu periksa ulang.",
            ),
            "OUTLOOK_SENDER_DUPLICATE": (
                "Data pengirim Outlook duplikat.",
                (
                    "Pastikan kombinasi workflow, company_code, branch_code, "
                    "dan sender_email hanya muncul satu kali."
                ),
            ),
            "OUTLOOK_SENDER_DUPLICATE_IDENTICAL_IGNORED": (
                "Salinan identik pengirim Outlook diabaikan.",
                "Importer memakai kemunculan pertama dari data yang sama.",
            ),
            "OUTLOOK_SENDER_ROW_INVALID": (
                "Format data pengirim Outlook tidak valid.",
                "Perbaiki nilai pada lokasi yang ditunjukkan, lalu periksa ulang.",
            ),
        }
        return mapping.get(code, (fallback, fallback))

    def commit(
        self,
        database_path: Path,
        request: ConfigImportCommitRequest,
    ):
        return self.importer.commit(database_path, request)

    def commit_preview(
        self,
        database_path: Path,
        preview,
        *,
        modules: tuple[str, ...],
        confirmed: bool,
    ):
        return self.commit(
            database_path,
            ConfigImportCommitRequest(
                preview,
                modules,
                ImportMode.REPLACE_MODULE_CONFIGURATION,
                confirmed=confirmed,
            ),
        )

    def export(
        self,
        database_path: Path,
        output_path: Path,
        *,
        overwrite: bool,
    ):
        return export_current_configuration(
            database_path,
            output_path,
            overwrite=overwrite,
            create_parent=False,
        )

    def save_template_copy(
        self,
        output_path: Path,
        *,
        overwrite: bool,
    ) -> Path:
        if output_path.exists() and not overwrite:
            raise FileExistsError(output_path)
        if not self.template_path.is_file():
            raise FileNotFoundError(self.template_path)
        shutil.copy2(self.template_path, output_path)
        return output_path

    @staticmethod
    def default_export_name() -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return f"OAS-K_Configuration_Export_{stamp}.xlsx"

    @staticmethod
    def file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
