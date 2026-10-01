"""Facade for read-only preview and explicit atomic commit."""

from __future__ import annotations

from pathlib import Path

from shared.database.importing.models import (
    ConfigImportCommitRequest,
    ConfigImportCommitResult,
    ConfigImportPreview,
)
from shared.database.importing.preview_builder import PreviewBuilder
from shared.database.importing.transaction_service import (
    ImportTransactionService,
)


class ConfigImportService:
    """Small DB2 facade with no implicit commit."""

    def __init__(
        self,
        preview_builder: PreviewBuilder | None = None,
        transaction_service: ImportTransactionService | None = None,
    ) -> None:
        self.preview_builder = preview_builder or PreviewBuilder()
        self.transaction_service = (
            transaction_service or ImportTransactionService()
        )

    def preview(
        self,
        database_path: str | Path,
        source_files: list[str | Path] | tuple[str | Path, ...],
        *,
        global_resolution: dict[str, object] | None = None,
    ) -> ConfigImportPreview:
        return self.preview_builder.build(
            database_path,
            source_files,
            global_resolution=global_resolution,
        )

    def commit(
        self,
        database_path: str | Path,
        request: ConfigImportCommitRequest,
    ) -> ConfigImportCommitResult:
        return self.transaction_service.commit(database_path, request)
