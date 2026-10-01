"""Explicit, previewed maintenance restricted to the active analytics database."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from shared.attendance_ot.backup import verified_backup
from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.time_utils import current_timestamp


@dataclass(frozen=True)
class MaintenancePreview:
    operation: str
    database: Path
    database_uuid: str
    date_from: str
    date_to: str
    counts: tuple[tuple[str, int], ...]
    revision: tuple

    def describe(self):
        return (
            f"{self.operation}: {self.database}\nPeriod: {self.date_from or 'ALL'} — {self.date_to or 'ALL'}\n"
            + "\n".join(f"{name}: {count:,}" for name, count in self.counts)
        )


@dataclass(frozen=True)
class DuplicatePreview:
    database: Path
    database_uuid: str
    duplicate_groups: int
    duplicate_rows: int
    samples: tuple[dict[str, object], ...]
    revision: tuple


class AttendanceOTMaintenanceService:
    TABLES = (
        "attendance_records",
        "employee_records",
        "schedule_records",
        "schedule_rule_records",
        "source_registry",
    )
    DUPLICATE_PARTITION = """
        upper(trim(emplid)),
        trim(date_in),
        COALESCE(trim(time_in), ''),
        COALESCE(trim(date_out), ''),
        COALESCE(trim(time_out), '')
    """

    def __init__(self, storage_service):
        self.storage_service = storage_service
        self.factory = SQLiteConnectionFactory()

    def _database(self):
        status = self.storage_service.resolve_status()
        if not status.database_valid or not status.database_path:
            raise RuntimeError("Database analytics belum siap.")
        path = Path(status.database_path).resolve()
        expected = self.storage_service.database_path(status.data_root).resolve()
        if path != expected or path.name != "attendance_ot.db":
            raise ValueError("Maintenance hanya untuk attendance_ot.db aktif.")
        return path

    def info(self):
        path = self._database()
        with self.factory.connect(path, read_only=True) as c:
            meta = dict(
                c.execute(
                    "SELECT database_uuid,schema_version,derived_refreshed_at,derived_dirty,derived_error FROM analytics_metadata WHERE metadata_id=1"
                ).fetchone()
            )
            count, low, high = c.execute(
                "SELECT COUNT(*),MIN(date_in),MAX(date_in) FROM attendance_records"
            ).fetchone()
            last = c.execute(
                "SELECT MAX(completed_at) FROM analytics_maintenance"
            ).fetchone()[0]
        return {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "record_count": count,
            "period_from": low,
            "period_to": high,
            "last_cleanup": last,
            **meta,
        }

    def preview_duplicates(self, *, sample_limit: int = 100) -> DuplicatePreview:
        if sample_limit < 0 or sample_limit > 1_000:
            raise ValueError("Duplicate sample limit harus 0..1000.")
        path = self._database()
        with self.factory.connect(path, read_only=True) as connection:
            connection.execute("BEGIN")
            return self._duplicate_preview(connection, path, sample_limit)

    def _duplicate_preview(
        self, connection, path: Path, sample_limit: int
    ) -> DuplicatePreview:
        metadata = connection.execute(
            """
            SELECT database_uuid, schema_version, derived_refreshed_at,
                   derived_dirty, last_migrated_at
            FROM analytics_metadata WHERE metadata_id=1
            """
        ).fetchone()
        if metadata is None:
            raise RuntimeError("Metadata analytics tidak ditemukan.")
        if metadata[3]:
            raise RuntimeError("Selesaikan Refresh Data sebelum cek duplikat.")

        groups, rows = connection.execute(
            f"""
            SELECT COUNT(*), COALESCE(SUM(group_rows - 1), 0)
            FROM (
                SELECT COUNT(*) AS group_rows
                FROM attendance_records
                WHERE trim(emplid) <> '' AND trim(COALESCE(date_in, '')) <> ''
                GROUP BY {self.DUPLICATE_PARTITION}
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()
        registry = connection.execute(
            """
            SELECT COUNT(*), MAX(updated_at), COALESCE(SUM(row_count), 0)
            FROM source_registry
            """
        ).fetchone()
        attendance = connection.execute(
            "SELECT COUNT(*), MAX(attendance_record_id) FROM attendance_records"
        ).fetchone()
        revision = (
            tuple(metadata),
            tuple(registry),
            tuple(attendance),
            int(groups),
            int(rows),
        )

        samples: tuple[dict[str, object], ...] = ()
        if sample_limit and rows:
            samples = tuple(
                dict(row)
                for row in connection.execute(
                    f"""
                    WITH ranked AS (
                        SELECT attendance_record_id, emplid, date_in, time_in,
                               date_out, time_out, source_file, source_sheet,
                               source_row,
                               ROW_NUMBER() OVER (
                                   PARTITION BY {self.DUPLICATE_PARTITION}
                                   ORDER BY attendance_record_id
                               ) AS duplicate_rank
                        FROM attendance_records
                        WHERE trim(emplid) <> ''
                          AND trim(COALESCE(date_in, '')) <> ''
                    )
                    SELECT attendance_record_id, emplid, date_in, time_in,
                           date_out, time_out, source_file, source_sheet,
                           source_row
                    FROM ranked WHERE duplicate_rank > 1
                    ORDER BY emplid, date_in, time_in, date_out, time_out,
                             attendance_record_id
                    LIMIT ?
                    """,
                    (sample_limit,),
                )
            )
        return DuplicatePreview(
            path,
            str(metadata[0]),
            int(groups),
            int(rows),
            samples,
            revision,
        )

    def delete_duplicates(self, preview: DuplicatePreview, *, confirmation: str):
        if confirmation != "DELETE DUPLICATES":
            raise ValueError("Konfirmasi eksplisit 'DELETE DUPLICATES' diperlukan.")
        path = self._database()
        if path != preview.database:
            raise RuntimeError("Data Root berubah. Jalankan cek duplikat kembali.")
        if preview.duplicate_rows == 0:
            return {"deleted_records": 0, "backup": None}

        backup = verified_backup(path, "before-deduplicate")
        with self.factory.connect(path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._duplicate_preview(connection, path, 0)
            if current.revision != preview.revision:
                raise RuntimeError(
                    "Data berubah sejak pengecekan duplikat. Jalankan cek kembali."
                )

            duplicate_ids = f"""
                SELECT attendance_record_id FROM (
                    SELECT attendance_record_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY {self.DUPLICATE_PARTITION}
                               ORDER BY attendance_record_id
                           ) AS duplicate_rank
                    FROM attendance_records
                    WHERE trim(emplid) <> ''
                      AND trim(COALESCE(date_in, '')) <> ''
                ) WHERE duplicate_rank > 1
            """
            connection.execute(
                "DELETE FROM enriched_attendance "
                f"WHERE attendance_record_id IN ({duplicate_ids})"
            )
            connection.execute(
                "DELETE FROM attendance_records "
                f"WHERE attendance_record_id IN ({duplicate_ids})"
            )
            connection.execute(
                """
                UPDATE source_registry
                SET row_count=(
                    SELECT COUNT(*) FROM attendance_records a
                    WHERE a.source_id=source_registry.source_id
                ), updated_at=?
                WHERE source_type='ATTENDANCE_OT'
                """,
                (current_timestamp(),),
            )
            self._rebuild_monthly_aggregate(connection)
            now = current_timestamp()
            connection.execute(
                """
                UPDATE analytics_metadata
                SET derived_dirty=0, derived_error=NULL, derived_refreshed_at=?
                WHERE metadata_id=1
                """,
                (now,),
            )
            connection.execute(
                """
                INSERT INTO analytics_maintenance (
                    operation, period_from, period_to, deleted_records,
                    completed_at, backup_path
                ) VALUES ('DEDUPLICATE', NULL, NULL, ?, ?, ?)
                """,
                (preview.duplicate_rows, now, str(backup)),
            )
            connection.commit()
        return {
            "deleted_records": preview.duplicate_rows,
            "backup": str(backup),
        }

    @staticmethod
    def _rebuild_monthly_aggregate(connection) -> None:
        connection.execute("DELETE FROM analytics_monthly_employee")
        connection.execute(
            """
            INSERT INTO analytics_monthly_employee (
                year_month, emplid, employee_name, classification, branch,
                department, division, pay_group, total_records, late_count,
                total_ot_minutes, ot_amount, meal_ot_amount
            )
            SELECT substr(attendance_date,1,7), emplid,
                   COALESCE(employee_name,''), COALESCE(classification,''),
                   COALESCE(branch,''), COALESCE(department,''),
                   COALESCE(division,''), COALESCE(pay_group,''), COUNT(*),
                   SUM(CASE WHEN late_status='LATE' THEN 1 ELSE 0 END),
                   SUM(total_ot_minutes), SUM(ot_amount), SUM(meal_ot_amount)
            FROM enriched_attendance
            GROUP BY substr(attendance_date,1,7), emplid,
                     COALESCE(employee_name,''), COALESCE(classification,''),
                     COALESCE(branch,''), COALESCE(department,''),
                     COALESCE(division,''), COALESCE(pay_group,'')
            """
        )

    def preview(self, operation, date_from="", date_to=""):
        if operation not in ("PURGE", "RESET"):
            raise ValueError("Operasi tidak valid.")
        if operation == "PURGE":
            date.fromisoformat(date_from)
            date.fromisoformat(date_to)
            if date_from > date_to:
                raise ValueError("Period awal harus <= akhir.")
        path = self._database()
        with self.factory.connect(path, read_only=True) as c:
            c.execute("BEGIN")
            return self._preview(c, path, operation, date_from, date_to)

    def _preview(self, c, path, operation, low, high):
        meta = c.execute(
            "SELECT database_uuid,derived_refreshed_at,derived_dirty,last_migrated_at FROM analytics_metadata WHERE metadata_id=1"
        ).fetchone()
        if meta[2]:
            raise RuntimeError("Selesaikan Refresh Data sebelum maintenance.")
        all_counts = tuple(
            (table, c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in self.TABLES
        )
        if operation == "PURGE":
            count = c.execute(
                "SELECT COUNT(*) FROM attendance_records WHERE date_in>=? AND date_in<=?",
                (low, high),
            ).fetchone()[0]
            counts = (("attendance_records", count),)
        else:
            counts = all_counts
        registry = c.execute(
            "SELECT MAX(updated_at),MAX(source_id),SUM(size_bytes),SUM(row_count) FROM source_registry"
        ).fetchone()
        cleanup = c.execute(
            "SELECT MAX(event_id) FROM analytics_maintenance"
        ).fetchone()[0]
        return MaintenancePreview(
            operation,
            path,
            meta[0],
            low,
            high,
            counts,
            (tuple(meta), all_counts, tuple(registry), cleanup),
        )

    def execute(self, preview, *, confirmation):
        if confirmation != preview.operation:
            raise ValueError(f"Konfirmasi eksplisit '{preview.operation}' diperlukan.")
        path = self._database()
        if path != preview.database:
            raise RuntimeError("Data Root berubah. Buat preview baru.")
        backup = verified_backup(path, preview.operation.lower())
        with self.factory.connect(path) as c:
            c.execute("BEGIN IMMEDIATE")
            current = self._preview(
                c, path, preview.operation, preview.date_from, preview.date_to
            )
            if current != preview:
                raise RuntimeError(
                    "Data berubah sejak preview. Periksa summary baru sebelum konfirmasi."
                )
            if preview.operation == "RESET":
                for table in (
                    "analytics_monthly_employee",
                    "enriched_attendance",
                    "employee_snapshots",
                    "schedule_rule_master",
                    *self.TABLES,
                ):
                    c.execute(f"DELETE FROM {table}")
                deleted = dict(preview.counts)["attendance_records"]
            else:
                args = (preview.date_from, preview.date_to)
                c.execute(
                    "DELETE FROM enriched_attendance WHERE attendance_record_id IN (SELECT attendance_record_id FROM attendance_records WHERE date_in>=? AND date_in<=?)",
                    args,
                )
                deleted = c.execute(
                    "DELETE FROM attendance_records WHERE date_in>=? AND date_in<=?",
                    args,
                ).rowcount
                c.execute(
                    "UPDATE source_registry SET row_count=(SELECT COUNT(*) FROM attendance_records a WHERE a.source_id=source_registry.source_id) WHERE source_type='ATTENDANCE_OT'"
                )
                c.execute("DELETE FROM analytics_monthly_employee")
                c.execute("""INSERT INTO analytics_monthly_employee SELECT substr(attendance_date,1,7),emplid,
                    COALESCE(employee_name,''),COALESCE(classification,''),COALESCE(branch,''),
                    COALESCE(department,''),COALESCE(division,''),COALESCE(pay_group,''),COUNT(*),
                    SUM(CASE WHEN late_status='LATE' THEN 1 ELSE 0 END),SUM(total_ot_minutes),SUM(ot_amount),SUM(meal_ot_amount)
                    FROM enriched_attendance GROUP BY 1,2,3,4,5,6,7,8""")
            now = current_timestamp()
            c.execute(
                "UPDATE analytics_metadata SET derived_dirty=0,derived_error=NULL,derived_refreshed_at=? WHERE metadata_id=1",
                (now,),
            )
            c.execute(
                "INSERT INTO analytics_maintenance(operation,period_from,period_to,deleted_records,completed_at,backup_path) VALUES(?,?,?,?,?,?)",
                (
                    preview.operation,
                    preview.date_from,
                    preview.date_to,
                    deleted,
                    now,
                    str(backup),
                ),
            )
        return {"deleted_records": deleted, "backup": str(backup)}

    def vacuum(self):
        path = self._database()
        with self.factory.connect(path) as c:
            c.execute("VACUUM")
            c.execute(
                "INSERT INTO analytics_maintenance(operation,deleted_records,completed_at) VALUES('VACUUM',0,?)",
                (current_timestamp(),),
            )
        return self.info()
