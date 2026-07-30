"""Post-update health check marker handling."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.constants import SCHEMA_VERSION
from shared.database.time_utils import current_timestamp
from shared.logger import get_logger
from shared.storage.data_root_manager import DataRootManager
from shared.storage.registry import StorageRegistryService, WindowsRegistryBackend
from shared.update.exceptions import UpdateHealthCheckError
from shared.update.models import HealthCheckResult
from shared.update.transaction_store import UpdateTransactionStore

logger = get_logger(__name__)


class PostUpdateHealthCheck:
    def __init__(
        self,
        *,
        application_version: str,
        connection_factory: SQLiteConnectionFactory | None = None,
    ) -> None:
        self.application_version = application_version
        self.connection_factory = connection_factory or SQLiteConnectionFactory()

    def run(
        self,
        transaction_path: str | Path,
        *,
        create_ui_shell: bool = False,
    ) -> HealthCheckResult:
        data_root = _data_root_from_transaction_path(Path(transaction_path))
        store = UpdateTransactionStore(data_root)
        transaction = store.load(transaction_path)
        checks = {
            "application_version": self.application_version == transaction.target_version,
            "application_root": transaction.application_root.is_dir(),
            "data_root": data_root.is_dir(),
            "database_open": False,
            "schema_compatible": False,
            "logger_write": False,
            "ui_shell_created": not create_ui_shell,
        }
        errors: list[str] = []
        database_schema_version = None
        try:
            registry = StorageRegistryService(WindowsRegistryBackend())
            active_database = DataRootManager(registry).get_active_database_path()
            database_path = active_database or data_root / "database" / "OAS-K.db"
            with self.connection_factory.connect(database_path, read_only=True) as connection:
                quick = connection.execute("PRAGMA quick_check").fetchone()
                checks["database_open"] = quick is not None and str(quick[0]).casefold() == "ok"
                row = connection.execute(
                    "SELECT schema_version FROM database_metadata WHERE metadata_id=1"
                ).fetchone()
                database_schema_version = int(row[0]) if row is not None else None
                checks["schema_compatible"] = database_schema_version == SCHEMA_VERSION
        except Exception as exc:
            errors.append(f"database={type(exc).__name__}: {exc}")
        try:
            marker = data_root / "update" / "logs" / ".healthcheck_logger_write"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(current_timestamp(), encoding="utf-8")
            marker.unlink(missing_ok=True)
            logger.info("Post-update logger write check completed.")
            checks["logger_write"] = True
        except Exception as exc:
            errors.append(f"logger={type(exc).__name__}: {exc}")
        if create_ui_shell:
            try:
                import tkinter as tk
                from ui.app import OASKUnifiedApp

                root = tk.Tk()
                root.withdraw()
                app = OASKUnifiedApp(root=root)
                app.close()
                checks["ui_shell_created"] = True
            except Exception as exc:
                errors.append(f"ui_shell={type(exc).__name__}: {exc}")
        status = "SUCCESS" if all(checks.values()) else "FAILED"
        result = HealthCheckResult(
            transaction_id=transaction.transaction_id,
            status=status,
            application_version=self.application_version,
            database_schema_version=database_schema_version,
            checked_at=current_timestamp(),
            checks=checks,
            marker_path=Path(transaction_path).parent / "healthcheck_success.json",
            errors=tuple(errors),
        )
        if status != "SUCCESS":
            raise UpdateHealthCheckError("; ".join(errors) or "Post-update health check failed.")
        self.write_success_marker(result)
        store.update_status(transaction, "SUCCESS")
        return result

    @staticmethod
    def write_success_marker(result: HealthCheckResult) -> None:
        if result.marker_path is None:
            raise UpdateHealthCheckError("Health-check marker path kosong.")
        payload = {
            "transaction_id": result.transaction_id,
            "status": result.status,
            "application_version": result.application_version,
            "database_schema_version": result.database_schema_version,
            "checked_at": result.checked_at,
            "checks": result.checks,
        }
        _atomic_json(result.marker_path, payload)


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file_handle:
            json.dump(payload, file_handle, indent=2, sort_keys=True)
            file_handle.write("\n")
            file_handle.flush()
            os.fsync(file_handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _data_root_from_transaction_path(path: Path) -> Path:
    resolved = path.resolve()
    transactions = resolved.parents[1]
    update_root = transactions.parent
    if transactions.name != "transactions" or update_root.name != "update":
        raise UpdateHealthCheckError("Transaction path layout invalid.")
    return update_root.parent
