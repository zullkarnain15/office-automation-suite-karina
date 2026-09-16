"""HKCU Registry adapter and typed storage-pointer service."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from shared.storage.constants import (
    REGISTRY_DATABASE_PATH_VALUE,
    REGISTRY_DATA_ROOT_VALUE,
    REGISTRY_KEY,
)
from shared.storage.exceptions import (
    RegistryAccessError,
    RegistryPointerMalformedError,
)
from shared.storage.models import StoragePointer
from shared.storage.path_resolver import get_database_path
from shared.storage.registry.backend import RegistryBackend

try:
    import winreg
except ImportError:  # pragma: no cover - exercised on non-Windows CI
    winreg = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class WindowsRegistryBackend:
    """Minimal HKCU-only winreg adapter, instantiated explicitly."""

    def __init__(self, module: Any = None) -> None:
        self.winreg = module if module is not None else winreg
        if self.winreg is None:
            raise RegistryAccessError(
                "Windows Registry is not supported on this platform."
            )

    def read_value(self, key: str, name: str) -> str | None:
        try:
            with self.winreg.OpenKey(
                self.winreg.HKEY_CURRENT_USER,
                key,
                0,
                self.winreg.KEY_READ,
            ) as handle:
                value, value_type = self.winreg.QueryValueEx(handle, name)
        except FileNotFoundError:
            return None
        except (OSError, PermissionError) as exc:
            raise RegistryAccessError(
                "Unable to read the OAS-K storage pointer."
            ) from exc
        if value_type != self.winreg.REG_SZ or not isinstance(value, str):
            raise RegistryPointerMalformedError(
                "Storage pointer Registry value is not a string."
            )
        return value

    def write_values(self, key: str, values: dict[str, str]) -> None:
        try:
            with self.winreg.CreateKeyEx(
                self.winreg.HKEY_CURRENT_USER,
                key,
                0,
                self.winreg.KEY_SET_VALUE,
            ) as handle:
                for name, value in values.items():
                    self.winreg.SetValueEx(
                        handle,
                        name,
                        0,
                        self.winreg.REG_SZ,
                        value,
                    )
        except (OSError, PermissionError) as exc:
            raise RegistryAccessError(
                "Unable to write the OAS-K storage pointer."
            ) from exc

    def delete_key(self, key: str) -> None:
        try:
            self.winreg.DeleteKey(self.winreg.HKEY_CURRENT_USER, key)
        except FileNotFoundError:
            return
        except (OSError, PermissionError) as exc:
            raise RegistryAccessError(
                "Unable to clear the OAS-K storage pointer."
            ) from exc

    def key_exists(self, key: str) -> bool:
        try:
            with self.winreg.OpenKey(
                self.winreg.HKEY_CURRENT_USER,
                key,
                0,
                self.winreg.KEY_READ,
            ):
                return True
        except FileNotFoundError:
            return False
        except (OSError, PermissionError) as exc:
            raise RegistryAccessError(
                "Unable to inspect the OAS-K storage pointer."
            ) from exc


class StorageRegistryService:
    """Read and write the two approved HKCU values only."""

    def __init__(self, backend: RegistryBackend) -> None:
        self.backend = backend

    def read_storage_pointer(self) -> StoragePointer | None:
        data_root_value = self.backend.read_value(
            REGISTRY_KEY,
            REGISTRY_DATA_ROOT_VALUE,
        )
        database_value = self.backend.read_value(
            REGISTRY_KEY,
            REGISTRY_DATABASE_PATH_VALUE,
        )
        if data_root_value is None and database_value is None:
            return None
        if (
            not isinstance(data_root_value, str)
            or not isinstance(database_value, str)
            or not data_root_value
            or not database_value
        ):
            raise RegistryPointerMalformedError(
                "Storage pointer is incomplete."
            )
        data_root = Path(data_root_value).expanduser()
        database_path = Path(database_value).expanduser()
        if not data_root.is_absolute() or not database_path.is_absolute():
            raise RegistryPointerMalformedError(
                "Storage pointer paths must be absolute."
            )
        if database_path.resolve() != get_database_path(data_root).resolve():
            raise RegistryPointerMalformedError(
                "DatabasePath does not match DataRoot."
            )
        logger.info("OAS-K storage pointer read from HKCU.")
        return StoragePointer(
            data_root=data_root,
            database_path=database_path,
        )

    def write_storage_pointer(
        self,
        data_root: str | Path,
        database_path: str | Path,
    ) -> StoragePointer:
        root = Path(data_root).expanduser()
        database = Path(database_path).expanduser()
        if not root.is_absolute() or not database.is_absolute():
            raise RegistryPointerMalformedError(
                "Storage pointer paths must be absolute."
            )
        if database.resolve() != get_database_path(root).resolve():
            raise RegistryPointerMalformedError(
                "DatabasePath does not match DataRoot."
            )
        previous_data_root = self.backend.read_value(
            REGISTRY_KEY,
            REGISTRY_DATA_ROOT_VALUE,
        )
        previous_database = self.backend.read_value(
            REGISTRY_KEY,
            REGISTRY_DATABASE_PATH_VALUE,
        )
        try:
            self.backend.write_values(
                REGISTRY_KEY,
                {
                    REGISTRY_DATA_ROOT_VALUE: str(root),
                    REGISTRY_DATABASE_PATH_VALUE: str(database),
                },
            )
        except RegistryAccessError:
            try:
                if previous_data_root and previous_database:
                    self.backend.write_values(
                        REGISTRY_KEY,
                        {
                            REGISTRY_DATA_ROOT_VALUE: previous_data_root,
                            REGISTRY_DATABASE_PATH_VALUE: previous_database,
                        },
                    )
                elif previous_data_root is None and previous_database is None:
                    self.backend.delete_key(REGISTRY_KEY)
            except RegistryAccessError:
                logger.exception(
                    "Unable to restore previous HKCU storage pointer."
                )
            raise
        logger.info("OAS-K storage pointer written to HKCU.")
        return StoragePointer(root, database)

    def clear_storage_pointer(self) -> None:
        self.backend.delete_key(REGISTRY_KEY)
        logger.info("OAS-K storage pointer cleared from HKCU.")

    def storage_pointer_exists(self) -> bool:
        return self.backend.key_exists(REGISTRY_KEY)
