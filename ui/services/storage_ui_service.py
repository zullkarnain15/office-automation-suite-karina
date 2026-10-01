"""Storage facade for read-only resolution and explicit DB3 actions."""

from __future__ import annotations

from pathlib import Path

from shared.database import (
    DatabaseValidator,
    SQLiteConnectionFactory,
    StartupDatabaseMigrator,
)
from shared.storage import (
    DataLocationChangeRequest,
    DataLocationManager,
    DataRootManager,
    StorageBootstrapRequest,
    StorageBootstrapService,
)
from shared.storage.path_resolver import resolve_storage_layout
from shared.storage.registry import StorageRegistryService
from shared.storage.constants import DEFAULT_DATA_ROOT
from ui.services.protocols import StorageStatusView


class StorageUIService:
    def __init__(
        self,
        registry: StorageRegistryService,
        *,
        application_version: str,
        default_data_root: Path = DEFAULT_DATA_ROOT,
    ) -> None:
        self.registry = registry
        self.application_version = application_version
        self.default_data_root = default_data_root
        self.validator = DatabaseValidator()
        self.startup_migrator = StartupDatabaseMigrator()

    def prepare_startup_database(self, *, progress=None):
        resolution = DataRootManager(
            self.registry,
            default_data_root=self.default_data_root,
        ).resolve_startup_storage()
        backup_root = (
            resolve_storage_layout(resolution.data_root).backup_root
            if resolution.data_root is not None
            else None
        )
        return self.startup_migrator.ensure_current(
            resolution.database_path,
            backup_root,
            progress=progress,
        )

    def resolve_status(self) -> StorageStatusView:
        try:
            resolution = DataRootManager(
                self.registry,
                default_data_root=self.default_data_root,
            ).resolve_startup_storage()
            registry_status = "Tersedia"
        except Exception as exc:
            return StorageStatusView(
                "REGISTRY_UNAVAILABLE",
                None,
                None,
                False,
                False,
                None,
                None,
                "Tidak tersedia",
                None,
                None,
                None,
                None,
                None,
                errors=(str(exc),),
            )
        root = resolution.data_root
        database = resolution.database_path
        layout = resolve_storage_layout(root) if root else None
        validation = (
            self.validator.validate(database)
            if database is not None and database.is_file()
            else None
        )
        app_version = None
        if validation is not None and validation.is_valid and database:
            with SQLiteConnectionFactory().connect(
                database,
                read_only=True,
            ) as connection:
                row = connection.execute(
                    "SELECT application_version FROM database_metadata "
                    "WHERE metadata_id=1"
                ).fetchone()
                app_version = str(row[0]) if row else None
        return StorageStatusView(
            resolution.status.value,
            root,
            database,
            bool(database and database.is_file()),
            bool(validation and validation.is_valid),
            validation.schema_version if validation else None,
            app_version,
            registry_status,
            layout.hris_recorder_profiles_root if layout else None,
            layout.backup_root if layout else None,
            layout.output_root if layout else None,
            layout.logs_root if layout else None,
            layout.diagnostics_root if layout else None,
            resolution.warnings,
            resolution.errors,
        )

    def initialize(self, data_root: Path, *, write_registry: bool):
        return StorageBootstrapService(self.registry).initialize_storage(
            StorageBootstrapRequest(
                data_root,
                self.application_version,
                update_registry=write_registry,
            )
        )

    def relocate(self, request: DataLocationChangeRequest):
        return DataLocationManager(self.registry).change_data_location(request)

    def relocate_to(
        self,
        source: Path,
        target: Path,
        *,
        copy_recorder_profiles: bool = True,
        copy_output: bool = False,
        copy_logs: bool = False,
    ):
        return self.relocate(
            DataLocationChangeRequest(
                source,
                target,
                copy_database=True,
                copy_recorder_profiles=copy_recorder_profiles,
                copy_output=copy_output,
                copy_logs=copy_logs,
            )
        )

    def validate_database(self, database_path: Path):
        return self.validator.validate(database_path)
