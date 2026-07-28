"""Candidate database validation dialog."""

from ui.dialogs.operation_result_dialog import OperationResultDialog


class CandidateValidationDialog(OperationResultDialog):
    def __init__(self, parent, result) -> None:
        lines = (
            f"Candidate: {result.candidate_path.name}",
            f"SQLite: {result.sqlite_valid}",
            f"Integrity: {result.integrity_ok}",
            f"Foreign Keys: {result.foreign_keys_ok}",
            f"Schema Compatible: {result.schema_compatible}",
            f"Required Tables: {result.required_tables_ok}",
            f"Can Activate: {result.can_activate}",
            *(result.warnings or ()),
            *(result.errors or ()),
        )
        super().__init__(parent, "Validasi Candidate", tuple(lines))
