"""Validated export and atomic replacement for the analytics database."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import uuid
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from shared.attendance_ot.backup import verified_backup
from shared.attendance_ot.enrichment import AttendanceOTEnrichmentService
from shared.attendance_ot.schema import (
    ANALYTICS_SCHEMA_VERSION,
    AnalyticsSchemaManager,
)
from shared.database.connection_factory import SQLiteConnectionFactory


REQUIRED_CURRENT_TABLES = frozenset(
    {
        "analytics_metadata",
        "source_registry",
        "source_file_registry",
        "data_update_status",
        "attendance_records",
        "employee_records",
        "schedule_records",
        "schedule_rule_records",
        "employee_snapshots",
        "schedule_rule_master",
        "enriched_attendance",
        "analytics_monthly_employee",
        "analytics_maintenance",
    }
)

COUNT_TABLES = (
    "attendance_records",
    "employee_records",
    "schedule_records",
    "schedule_rule_records",
    "enriched_attendance",
    "analytics_monthly_employee",
)


@dataclass(frozen=True, slots=True)
class AnalyticsDatabaseValidation:
    path: Path
    is_valid: bool
    integrity_ok: bool
    foreign_keys_ok: bool
    schema_version: int | None
    target_schema_version: int
    migration_required: bool
    database_uuid: str | None
    size_bytes: int
    derived_dirty: bool | None
    derived_refreshed_at: str | None
    period_from: str | None
    period_to: str | None
    counts: tuple[tuple[str, int], ...]
    source_file_count: int
    warnings: tuple[str, ...]
    errors: tuple[str, ...]

    def lines(self) -> tuple[str, ...]:
        return (
            f"File: {self.path}",
            f"Status: {'VALID' if self.is_valid else 'TIDAK VALID'}",
            f"Ukuran: {self.size_bytes:,} bytes",
            f"Integrity: {'OK' if self.integrity_ok else 'GAGAL'}",
            f"Foreign Keys: {'OK' if self.foreign_keys_ok else 'GAGAL'}",
            f"Schema: {self.schema_version or '-'} -> {self.target_schema_version}",
            f"Migration Required: {self.migration_required}",
            f"Database UUID: {self.database_uuid or '-'}",
            f"Derived Dirty: {self.derived_dirty}",
            f"Last Analytics Refresh: {self.derived_refreshed_at or '-'}",
            f"Period: {self.period_from or '-'} s.d. {self.period_to or '-'}",
            f"Registered Source Files: {self.source_file_count:,}",
            "",
            "Jumlah Data:",
            *(f"{name}: {count:,}" for name, count in self.counts),
            "",
            "Peringatan:",
            *(self.warnings or ("Tidak ada",)),
            "",
            "Error:",
            *(self.errors or ("Tidak ada",)),
        )


@dataclass(frozen=True, slots=True)
class AnalyticsDatabaseExportResult:
    destination: Path
    size_bytes: int
    sha256: str
    validation: AnalyticsDatabaseValidation


@dataclass(frozen=True, slots=True)
class AnalyticsDatabaseImportResult:
    active_database: Path
    previous_database_backup: Path | None
    source_schema_version: int
    schema_version: int
    migrated: bool
    rebuilt_analytics: bool
    validation: AnalyticsDatabaseValidation


class AttendanceOTDatabaseTransferService:
    """Move only a verified Attendance & OT database between workstations."""

    def __init__(
        self,
        storage_service,
        *,
        factory: SQLiteConnectionFactory | None = None,
    ) -> None:
        self.storage_service = storage_service
        self.factory = factory or SQLiteConnectionFactory()
        self.schema_manager = AnalyticsSchemaManager(self.factory)

    def validate_candidate(self, candidate: str | Path) -> AnalyticsDatabaseValidation:
        path = Path(candidate).expanduser()
        errors: list[str] = []
        warnings: list[str] = []
        integrity_ok = False
        foreign_keys_ok = False
        schema_version: int | None = None
        database_uuid: str | None = None
        derived_dirty: bool | None = None
        derived_refreshed_at: str | None = None
        period_from: str | None = None
        period_to: str | None = None
        counts: list[tuple[str, int]] = []
        source_file_count = 0
        size_bytes = 0

        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_file():
                raise ValueError("Kandidat bukan file database.")
            path = resolved
            size_bytes = path.stat().st_size
            if size_bytes <= 0:
                raise ValueError("File database kosong.")

            with self.factory.connect(path, read_only=True) as connection:
                quick_rows = connection.execute("PRAGMA quick_check").fetchall()
                integrity_ok = bool(quick_rows) and all(
                    str(row[0]).lower() == "ok" for row in quick_rows
                )
                if not integrity_ok:
                    errors.append("SQLite quick_check gagal.")

                foreign_key_rows = connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
                foreign_keys_ok = not foreign_key_rows
                if not foreign_keys_ok:
                    errors.append(
                        "Foreign-key check menemukan "
                        f"{len(foreign_key_rows):,} pelanggaran."
                    )

                schema_objects = connection.execute(
                    "SELECT type, name FROM sqlite_master "
                    "WHERE name NOT LIKE 'sqlite_%'"
                ).fetchall()
                tables = {
                    str(row["name"])
                    for row in schema_objects
                    if str(row["type"]) == "table"
                }
                triggers = tuple(
                    str(row["name"])
                    for row in schema_objects
                    if str(row["type"]) == "trigger"
                )
                if triggers:
                    errors.append(
                        "Database kandidat memiliki trigger yang tidak didukung: "
                        + ", ".join(triggers)
                    )
                if "analytics_metadata" not in tables:
                    errors.append("Tabel analytics_metadata tidak ditemukan.")
                else:
                    metadata_columns = {
                        str(row["name"])
                        for row in connection.execute(
                            "PRAGMA table_info(analytics_metadata)"
                        )
                    }
                    required_metadata = {"database_uuid", "schema_version"}
                    missing_metadata = required_metadata - metadata_columns
                    if missing_metadata:
                        errors.append(
                            "Kolom metadata wajib tidak ditemukan: "
                            + ", ".join(sorted(missing_metadata))
                        )
                    else:
                        selected = ["database_uuid", "schema_version"]
                        if "derived_dirty" in metadata_columns:
                            selected.append("derived_dirty")
                        if "derived_refreshed_at" in metadata_columns:
                            selected.append("derived_refreshed_at")
                        metadata = connection.execute(
                            "SELECT " + ",".join(selected)
                            + " FROM analytics_metadata WHERE metadata_id=1"
                        ).fetchone()
                        if metadata is None:
                            errors.append("Metadata analytics tidak ditemukan.")
                        else:
                            database_uuid = str(metadata["database_uuid"])
                            schema_version = int(metadata["schema_version"])
                            if "derived_dirty" in selected:
                                derived_dirty = bool(metadata["derived_dirty"])
                            if "derived_refreshed_at" in selected:
                                value = metadata["derived_refreshed_at"]
                                derived_refreshed_at = (
                                    str(value) if value is not None else None
                                )

                user_version = int(
                    connection.execute("PRAGMA user_version").fetchone()[0]
                )
                if schema_version is not None and user_version != schema_version:
                    errors.append(
                        "PRAGMA user_version tidak sama dengan schema metadata."
                    )
                if schema_version is not None:
                    if schema_version < 1:
                        errors.append("Schema analytics tidak valid.")
                    elif schema_version > ANALYTICS_SCHEMA_VERSION:
                        errors.append(
                            f"Schema v{schema_version} lebih baru dari aplikasi "
                            f"(v{ANALYTICS_SCHEMA_VERSION})."
                        )
                    elif schema_version == ANALYTICS_SCHEMA_VERSION:
                        missing_tables = REQUIRED_CURRENT_TABLES - tables
                        if missing_tables:
                            errors.append(
                                "Tabel analytics wajib tidak ditemukan: "
                                + ", ".join(sorted(missing_tables))
                            )
                    else:
                        warnings.append(
                            f"Schema v{schema_version} akan dimigrasikan di staging "
                            f"ke v{ANALYTICS_SCHEMA_VERSION}."
                        )

                for table in COUNT_TABLES:
                    if table in tables:
                        count = int(
                            connection.execute(
                                f'SELECT COUNT(*) FROM "{table}"'
                            ).fetchone()[0]
                        )
                        counts.append((table, count))
                if "attendance_records" in tables:
                    period_from, period_to = connection.execute(
                        "SELECT MIN(date_in), MAX(date_in) FROM attendance_records"
                    ).fetchone()
                    period_from = str(period_from) if period_from else None
                    period_to = str(period_to) if period_to else None
                if "source_registry" in tables:
                    source_file_count = int(
                        connection.execute(
                            "SELECT COUNT(*) FROM source_registry"
                        ).fetchone()[0]
                    )
                    if source_file_count:
                        warnings.append(
                            "Path source dari PC asal tetap tersimpan. Konfigurasi "
                            "source pada database core PC ini tidak akan ditimpa; "
                            "nama file unik akan dikaitkan ulang saat Data Update."
                        )
                if derived_dirty:
                    warnings.append(
                        "Derived analytics berstatus dirty dan akan dibangun ulang "
                        "di staging sebelum aktivasi."
                    )
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            errors.append(str(exc))

        return AnalyticsDatabaseValidation(
            path=path,
            is_valid=(
                integrity_ok
                and foreign_keys_ok
                and schema_version is not None
                and not errors
            ),
            integrity_ok=integrity_ok,
            foreign_keys_ok=foreign_keys_ok,
            schema_version=schema_version,
            target_schema_version=ANALYTICS_SCHEMA_VERSION,
            migration_required=(
                schema_version is not None
                and schema_version < ANALYTICS_SCHEMA_VERSION
            ),
            database_uuid=database_uuid,
            size_bytes=size_bytes,
            derived_dirty=derived_dirty,
            derived_refreshed_at=derived_refreshed_at,
            period_from=period_from,
            period_to=period_to,
            counts=tuple(counts),
            source_file_count=source_file_count,
            warnings=tuple(warnings),
            errors=tuple(dict.fromkeys(errors)),
        )

    def export_verified(
        self, destination: str | Path
    ) -> AnalyticsDatabaseExportResult:
        active = self._active_database(require_existing=True)
        active_validation = self.validate_candidate(active)
        if not active_validation.is_valid:
            raise RuntimeError(
                "Database analytics aktif tidak valid: "
                + "; ".join(active_validation.errors)
            )

        target = Path(destination).expanduser().resolve()
        if target == active:
            raise ValueError("Tujuan export tidak boleh database analytics aktif.")
        if not target.parent.is_dir():
            raise FileNotFoundError(f"Folder tujuan tidak tersedia: {target.parent}")
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            self._sqlite_backup(active, temporary)
            validation = self.validate_candidate(temporary)
            if not validation.is_valid:
                raise RuntimeError(
                    "Hasil export gagal validasi: "
                    + "; ".join(validation.errors)
                )
            os.replace(temporary, target)
            final_validation = self.validate_candidate(target)
            if not final_validation.is_valid:
                raise RuntimeError("Hasil export final gagal validasi.")
            return AnalyticsDatabaseExportResult(
                target,
                target.stat().st_size,
                self._sha256(target),
                final_validation,
            )
        finally:
            if temporary.exists():
                temporary.unlink()

    def import_candidate(
        self, candidate: str | Path
    ) -> AnalyticsDatabaseImportResult:
        source = Path(candidate).expanduser().resolve(strict=True)
        active = self._active_database(require_existing=False)
        if source == active:
            raise ValueError("Kandidat sama dengan database analytics aktif.")

        source_validation = self.validate_candidate(source)
        if not source_validation.is_valid or source_validation.schema_version is None:
            raise ValueError(
                "Database kandidat tidak valid: "
                + "; ".join(source_validation.errors)
            )

        analytics_root = self.storage_service.analytics_root(
            self.storage_service.storage_service.resolve_status().data_root
        ).resolve()
        cache_root = (analytics_root / "cache").resolve()
        cache_root.mkdir(parents=True, exist_ok=True)
        if analytics_root not in cache_root.parents:
            raise RuntimeError("Path staging analytics tidak aman.")

        migrated = source_validation.migration_required
        rebuilt = False
        previous_backup: Path | None = None
        active.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="database-import-", dir=cache_root
        ) as temporary_directory:
            stage = Path(temporary_directory) / "attendance_ot.db"
            self._sqlite_backup(source, stage)
            staged_validation = self.validate_candidate(stage)
            if not staged_validation.is_valid or staged_validation.schema_version is None:
                raise RuntimeError(
                    "Snapshot staging gagal validasi: "
                    + "; ".join(staged_validation.errors)
                )

            if staged_validation.migration_required:
                self.schema_manager.migrate_to_current(
                    stage, staged_validation.schema_version
                )

            current_validation = self.validate_candidate(stage)
            if not current_validation.is_valid:
                raise RuntimeError(
                    "Database staging gagal setelah migration: "
                    + "; ".join(current_validation.errors)
                )
            if current_validation.derived_dirty:
                AttendanceOTEnrichmentService(factory=self.factory).rebuild(stage)
                rebuilt = True

            final_stage_validation = self.validate_candidate(stage)
            if (
                not final_stage_validation.is_valid
                or final_stage_validation.schema_version
                != ANALYTICS_SCHEMA_VERSION
                or final_stage_validation.derived_dirty
            ):
                raise RuntimeError(
                    "Database staging belum siap diaktifkan: "
                    + "; ".join(final_stage_validation.errors)
                )

            if active.is_file():
                previous_backup = verified_backup(
                    active, "before-portable-import"
                )

            replacement = active.with_name(
                f".{active.name}.{uuid.uuid4().hex}.replacement"
            )
            try:
                self._sqlite_backup(stage, replacement)
                replacement_validation = self.validate_candidate(replacement)
                if not replacement_validation.is_valid:
                    raise RuntimeError("Replacement database gagal validasi.")
                self._activate_database(replacement, active)
                post_validation = self.validate_candidate(active)
                self._post_import_health_check(active, post_validation)
            except Exception:
                if replacement.exists():
                    replacement.unlink()
                self._restore_after_failed_import(active, previous_backup)
                raise

        return AnalyticsDatabaseImportResult(
            active_database=active,
            previous_database_backup=previous_backup,
            source_schema_version=source_validation.schema_version,
            schema_version=ANALYTICS_SCHEMA_VERSION,
            migrated=migrated,
            rebuilt_analytics=rebuilt,
            validation=self.validate_candidate(active),
        )

    def _active_database(self, *, require_existing: bool) -> Path:
        core_status = self.storage_service.storage_service.resolve_status()
        if core_status.data_root is None or not getattr(
            core_status, "database_valid", False
        ):
            raise RuntimeError("Data Root dan database core aktif belum siap.")
        expected = self.storage_service.database_path(
            Path(core_status.data_root)
        ).resolve()
        if expected.name != "attendance_ot.db":
            raise RuntimeError("Target database analytics tidak valid.")
        if require_existing and not expected.is_file():
            raise FileNotFoundError("Database analytics aktif belum tersedia.")
        return expected

    @staticmethod
    def _sqlite_backup(source: Path, destination: Path) -> None:
        if destination.exists():
            raise FileExistsError(f"File staging sudah ada: {destination}")
        try:
            with closing(
                sqlite3.connect(
                    f"{source.resolve().as_uri()}?mode=ro", uri=True
                )
            ) as source_connection:
                with closing(sqlite3.connect(destination)) as target_connection:
                    source_connection.backup(target_connection)
                    target_connection.commit()
                    quick = target_connection.execute(
                        "PRAGMA quick_check"
                    ).fetchall()
                    if not quick or any(
                        str(row[0]).lower() != "ok" for row in quick
                    ):
                        raise RuntimeError("Snapshot SQLite gagal quick_check.")
        except Exception:
            if destination.exists():
                destination.unlink()
            raise

    def _post_import_health_check(
        self,
        database: Path,
        validation: AnalyticsDatabaseValidation,
    ) -> None:
        if (
            not validation.is_valid
            or validation.schema_version != ANALYTICS_SCHEMA_VERSION
            or validation.derived_dirty
        ):
            raise RuntimeError("Post-import validation gagal.")
        with self.factory.connect(database, read_only=True) as connection:
            connection.execute(
                "SELECT COALESCE(SUM(total_records),0), "
                "COUNT(DISTINCT emplid) FROM analytics_monthly_employee"
            ).fetchone()
            connection.execute(
                "SELECT attendance_record_id FROM enriched_attendance LIMIT 1"
            ).fetchone()

    def _restore_after_failed_import(
        self,
        active: Path,
        previous_backup: Path | None,
    ) -> None:
        if previous_backup is None:
            if active.exists():
                active.unlink()
            return
        rollback = active.with_name(
            f".{active.name}.{uuid.uuid4().hex}.rollback"
        )
        try:
            self._sqlite_backup(previous_backup, rollback)
            self._activate_database(rollback, active)
            restored = self.validate_candidate(active)
            if not restored.is_valid:
                raise RuntimeError("Rollback database analytics gagal validasi.")
        finally:
            if rollback.exists():
                rollback.unlink()

    def _activate_database(self, replacement: Path, active: Path) -> None:
        """Prefer an atomic rename, with SQLite backup fallback on Windows."""

        try:
            os.replace(replacement, active)
            return
        except PermissionError:
            if not active.exists():
                raise

        # Windows denies os.replace while another short-lived read connection
        # still owns a file handle.  SQLite's online backup API replaces the
        # destination transactionally and cooperates with those readers.
        with closing(
            sqlite3.connect(
                f"{replacement.resolve().as_uri()}?mode=ro", uri=True
            )
        ) as source_connection:
            with closing(sqlite3.connect(active)) as target_connection:
                source_connection.backup(target_connection)
                target_connection.commit()
        replacement.unlink()

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
