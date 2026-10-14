"""Active Data Root selection and non-mutating startup resolution."""

from __future__ import annotations

import logging
from pathlib import Path

from shared.storage.constants import DEFAULT_DATA_ROOT
from shared.storage.exceptions import (
    RegistryAccessError,
    RegistryPointerMalformedError,
    StorageValidationError,
)
from shared.storage.models import (
    StartupStorageResolution,
    StartupStorageStatus,
    StorageLayout,
)
from shared.storage.path_resolver import resolve_storage_layout
from shared.storage.registry.windows_registry import StorageRegistryService
from shared.storage.storage_validator import validate_data_root

logger = logging.getLogger(__name__)


class DataRootManager:
    """Resolve Registry state or hold one explicit session-only root."""

    def __init__(
        self,
        registry: StorageRegistryService,
        *,
        default_data_root: Path = DEFAULT_DATA_ROOT,
    ) -> None:
        self.registry = registry
        self.default_data_root = default_data_root
        self._session_data_root: Path | None = None

    def validate_data_root(self, path: str | Path):
        return validate_data_root(path)

    def select_explicit_data_root(
        self,
        path: str | Path,
    ) -> StorageLayout:
        """Select a valid existing root for this process only."""

        validation = validate_data_root(path)
        if (
            not validation.exists
            or not validation.is_local
            or not validation.writable
        ):
            raise StorageValidationError(
                "Explicit Data Root is not an existing local writable folder."
            )
        self._session_data_root = validation.path
        return resolve_storage_layout(validation.path)

    use_explicit_data_root = select_explicit_data_root

    def get_active_data_root(self) -> Path | None:
        if self._session_data_root is not None:
            return self._session_data_root
        pointer = self.registry.read_storage_pointer()
        if pointer is None:
            return None
        validation = validate_data_root(pointer.data_root)
        if not validation.database_valid:
            raise StorageValidationError(
                "Persisted Data Root does not contain a valid active database."
            )
        return pointer.data_root

    def get_active_database_path(self) -> Path | None:
        if self._session_data_root is not None:
            return resolve_storage_layout(
                self._session_data_root
            ).database_path
        pointer = self.registry.read_storage_pointer()
        if pointer is None:
            return None
        validation = validate_data_root(pointer.data_root)
        if not validation.database_valid:
            raise StorageValidationError(
                "Persisted DatabasePath is not a valid OAS-K database."
            )
        return pointer.database_path

    def resolve_startup_storage(self) -> StartupStorageResolution:
        """Resolve state without creating directories, DB, or Registry values."""

        try:
            pointer = self.registry.read_storage_pointer()
        except RegistryPointerMalformedError as exc:
            logger.warning("Malformed OAS-K storage pointer.")
            return StartupStorageResolution(
                status=StartupStorageStatus.RECOVERY_REQUIRED,
                data_root=None,
                database_path=None,
                errors=(str(exc),),
            )
        except RegistryAccessError:
            logger.warning("Registry unavailable during storage resolution.")
            return StartupStorageResolution(
                status=StartupStorageStatus.REGISTRY_UNAVAILABLE,
                data_root=self._session_data_root,
                database_path=(
                    resolve_storage_layout(
                        self._session_data_root
                    ).database_path
                    if self._session_data_root is not None
                    else None
                ),
                warnings=("Registry is unavailable; use an explicit session path.",),
            )

        if pointer is not None:
            validation = validate_data_root(pointer.data_root)
            if validation.database_exists and validation.database_valid:
                status = StartupStorageStatus.READY
            elif validation.database_exists:
                status = StartupStorageStatus.RECOVERY_REQUIRED
            else:
                status = StartupStorageStatus.INVALID_LOCATION
            return StartupStorageResolution(
                status=status,
                data_root=pointer.data_root,
                database_path=pointer.database_path,
                validation=validation,
                warnings=validation.warnings,
                errors=validation.errors,
            )

        default_validation = validate_data_root(self.default_data_root)
        if (
            default_validation.database_exists
            and default_validation.database_valid
        ):
            status = StartupStorageStatus.AVAILABLE_NOT_REGISTERED
        elif default_validation.database_exists:
            status = StartupStorageStatus.RECOVERY_REQUIRED
        else:
            status = StartupStorageStatus.INITIAL_SETUP_REQUIRED
        return StartupStorageResolution(
            status=status,
            data_root=self.default_data_root,
            database_path=resolve_storage_layout(
                self.default_data_root
            ).database_path,
            validation=default_validation,
            warnings=default_validation.warnings,
            errors=default_validation.errors,
        )


def resolve_startup_storage(
    registry: StorageRegistryService,
    *,
    default_data_root: Path = DEFAULT_DATA_ROOT,
) -> StartupStorageResolution:
    return DataRootManager(
        registry,
        default_data_root=default_data_root,
    ).resolve_startup_storage()
