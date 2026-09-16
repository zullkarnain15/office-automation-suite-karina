"""Explicit first-run folder and schema-v1 database bootstrap."""

from __future__ import annotations

import logging
from pathlib import Path

from shared.database import DatabaseValidator, SchemaManager
from shared.storage.exceptions import (
    RegistryAccessError,
    StorageValidationError,
)
from shared.storage.models import (
    StorageBootstrapRequest,
    StorageBootstrapResult,
    StorageLayout,
)
from shared.storage.path_resolver import resolve_storage_layout
from shared.storage.registry.windows_registry import StorageRegistryService
from shared.storage.storage_validator import validate_data_root

logger = logging.getLogger(__name__)


def initialize_data_root(path: str | Path) -> tuple[StorageLayout, tuple[Path, ...]]:
    """Create only the standard directory structure, never a database."""

    validation = validate_data_root(path)
    if not validation.can_initialize:
        raise StorageValidationError(
            "Data Root cannot be initialized: "
            + "; ".join(validation.errors)
        )
    layout = resolve_storage_layout(validation.path)
    created: list[Path] = []
    for directory in layout.directories:
        if not directory.exists():
            directory.mkdir()
            created.append(directory)
    return layout, tuple(created)


class StorageBootstrapService:
    """Create a valid database only after an explicit caller request."""

    def __init__(
        self,
        registry: StorageRegistryService | None,
        *,
        schema_manager: SchemaManager | None = None,
        database_validator: DatabaseValidator | None = None,
    ) -> None:
        self.registry = registry
        self.schema_manager = schema_manager or SchemaManager()
        self.database_validator = (
            database_validator or DatabaseValidator()
        )

    def initialize_storage(
        self,
        request: StorageBootstrapRequest,
    ) -> StorageBootstrapResult:
        root = Path(request.data_root).expanduser()
        layout = resolve_storage_layout(root)
        created_directories: tuple[Path, ...] = ()
        database_created = False
        registry_updated = False
        warnings: list[str] = []
        errors: list[str] = []
        logger.info("Storage bootstrap started: %s", root)

        try:
            before = validate_data_root(
                root,
                database_validator=self.database_validator,
            )
            if not before.can_initialize:
                return self._result(
                    layout,
                    created_directories,
                    database_created,
                    registry_updated,
                    warnings,
                    list(before.errors),
                )

            layout, created_directories = initialize_data_root(root)
            if layout.database_path.exists():
                database_validation = self.database_validator.validate(
                    layout.database_path
                )
                if not database_validation.is_valid:
                    errors.append(
                        "Existing database is invalid and was not overwritten."
                    )
                    return self._result(
                        layout,
                        created_directories,
                        database_created,
                        registry_updated,
                        warnings,
                        errors,
                    )
            else:
                self.schema_manager.initialize_database(
                    layout.database_path,
                    request.application_version,
                )
                database_created = True

            final_validation = self.database_validator.validate(
                layout.database_path
            )
            if not final_validation.is_valid:
                errors.append(
                    "Bootstrapped database failed validation: "
                    + "; ".join(final_validation.errors)
                )
                return self._result(
                    layout,
                    created_directories,
                    database_created,
                    registry_updated,
                    warnings,
                    errors,
                )

            if request.update_registry:
                if self.registry is None:
                    warnings.append(
                        "Registry unavailable; use this Data Root for the current session."
                    )
                else:
                    try:
                        self.registry.write_storage_pointer(
                            layout.data_root,
                            layout.database_path,
                        )
                        registry_updated = True
                    except RegistryAccessError:
                        warnings.append(
                            "Registry update failed; database remains valid for explicit session use."
                        )
            logger.info("Storage bootstrap completed: %s", root)
        except Exception as exc:
            logger.exception("Storage bootstrap failed: %s", root)
            errors.append(f"Storage bootstrap failed: {exc}")

        return self._result(
            layout,
            created_directories,
            database_created,
            registry_updated,
            warnings,
            errors,
        )

    @staticmethod
    def _result(
        layout: StorageLayout,
        created_directories: tuple[Path, ...],
        database_created: bool,
        registry_updated: bool,
        warnings: list[str],
        errors: list[str],
    ) -> StorageBootstrapResult:
        return StorageBootstrapResult(
            success=not errors,
            data_root=layout.data_root,
            database_path=layout.database_path,
            created_directories=created_directories,
            database_created=database_created,
            registry_updated=registry_updated,
            warnings=tuple(warnings),
            errors=tuple(errors),
        )


def initialize_storage(
    request: StorageBootstrapRequest,
    *,
    registry: StorageRegistryService | None = None,
) -> StorageBootstrapResult:
    return StorageBootstrapService(registry).initialize_storage(request)
