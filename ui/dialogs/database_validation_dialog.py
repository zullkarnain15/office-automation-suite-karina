"""Detailed database validation view."""

from __future__ import annotations

from ui.dialogs.operation_result_dialog import OperationResultDialog


class DatabaseValidationDialog(OperationResultDialog):
    def __init__(self, parent, result) -> None:
        lines = (
            f"Integrity: {'OK' if result.integrity_ok else 'GAGAL'}",
            f"Foreign Keys: {'OK' if result.foreign_keys_ok else 'GAGAL'}",
            f"Schema Version: {result.schema_version or '-'}",
            f"Required Tables: {'OK' if not result.missing_tables else 'GAGAL'}",
            f"Metadata: {'OK' if result.schema_version else 'GAGAL'}",
            "",
            "Warnings:",
            *(result.warnings or ("Tidak ada",)),
            "",
            "Errors:",
            *(result.errors or ("Tidak ada",)),
        )
        super().__init__(parent, "Hasil Validasi Database", tuple(lines))
