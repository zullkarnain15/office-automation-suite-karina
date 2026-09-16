"""Reusable UI2 detail dialogs."""

from ui.dialogs.configuration_import_preview import (
    ConfigurationImportPreviewDialog,
)
from ui.dialogs.completion_popup import CompletionPopup
from ui.dialogs.database_validation_dialog import DatabaseValidationDialog
from ui.dialogs.operation_result_dialog import OperationResultDialog

__all__ = [
    "ConfigurationImportPreviewDialog",
    "CompletionPopup",
    "DatabaseValidationDialog",
    "OperationResultDialog",
]
