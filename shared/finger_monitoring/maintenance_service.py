"""Previewed, transactional maintenance for finger_monitoring.db only."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from shared.database.time_utils import current_timestamp


@dataclass(frozen=True, slots=True)
class CleanupPreview:
    retention_days: int | None
    cutoff_date: str | None
    result_count: int
    cycle_count: int
    revision: tuple[int, int, int, int]


class FingerMonitoringMaintenanceService:
    def __init__(self, repository, monitoring_root: Path, *, activity_gate=None, now=None) -> None:
        self.repository = repository
        self.monitoring_root = Path(monitoring_root)
        self.activity_gate = activity_gate
        self.now = now or datetime.now

    def preview_cleanup(self, retention_days: int | None = 90) -> CleanupPreview:
        if retention_days not in {30, 90, 180, None}:
            raise ValueError("Retention harus 30, 90, 180 hari, atau All History.")
        cutoff = None if retention_days is None else (self.now().date() - timedelta(days=retention_days)).isoformat()
        with self.repository.factory.connect(self.repository.database_path, read_only=True) as connection:
            where, args = ("1=1", ()) if cutoff is None else ("substr(checked_at,1,10) < ?", (cutoff,))
            results = int(connection.execute(f"SELECT COUNT(*) FROM check_result WHERE {where}", args).fetchone()[0])
            cycle_where, cycle_args = ("1=1", ()) if cutoff is None else ("substr(COALESCE(completed_at,started_at),1,10) < ?", (cutoff,))
            cycles = int(connection.execute(f"""SELECT COUNT(*) FROM check_cycle c WHERE {cycle_where}
                AND NOT EXISTS(SELECT 1 FROM device_daily_failure f WHERE f.first_cycle_id=c.cycle_id OR f.last_cycle_id=c.cycle_id)
                AND NOT EXISTS(SELECT 1 FROM email_delivery e WHERE e.cycle_id=c.cycle_id)""", cycle_args).fetchone()[0])
            revision = self._revision(connection)
        return CleanupPreview(retention_days, cutoff, results, cycles, revision)

    def cleanup(self, preview: CleanupPreview) -> dict[str, int]:
        context = self.activity_gate.exclusive("CLEANUP") if self.activity_gate else _null_context()
        with context, self.repository.factory.connect(self.repository.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if self._revision(connection) != preview.revision:
                raise RuntimeError("History berubah setelah preview. Buat preview baru.")
            where, args = ("1=1", ()) if preview.cutoff_date is None else ("substr(checked_at,1,10) < ?", (preview.cutoff_date,))
            deleted_results = connection.execute(f"DELETE FROM check_result WHERE {where}", args).rowcount
            cycle_where, cycle_args = ("1=1", ()) if preview.cutoff_date is None else ("substr(COALESCE(completed_at,started_at),1,10) < ?", (preview.cutoff_date,))
            deleted_cycles = connection.execute(f"""DELETE FROM check_cycle WHERE {cycle_where}
                AND NOT EXISTS(SELECT 1 FROM check_result r WHERE r.cycle_id=check_cycle.cycle_id)
                AND NOT EXISTS(SELECT 1 FROM device_daily_failure f WHERE f.first_cycle_id=check_cycle.cycle_id OR f.last_cycle_id=check_cycle.cycle_id)
                AND NOT EXISTS(SELECT 1 FROM email_delivery e WHERE e.cycle_id=check_cycle.cycle_id)""", cycle_args).rowcount
            connection.execute(
                "INSERT INTO maintenance_audit(operation,started_at,completed_at,status,detail) VALUES('CLEANUP',?,?, 'COMPLETED',?)",
                (current_timestamp(), current_timestamp(), f"results={deleted_results};cycles={deleted_cycles};retention={preview.retention_days}"),
            )
        return {"deleted_results": deleted_results, "deleted_cycles": deleted_cycles}

    def reset_monitoring_data(self, *, confirmation: str) -> dict[str, int]:
        if confirmation != "RESET MONITORING DATA":
            raise ValueError("Konfirmasi eksplisit 'RESET MONITORING DATA' diperlukan.")
        context = self.activity_gate.exclusive("RESET") if self.activity_gate else _null_context()
        with context, self.repository.factory.connect(self.repository.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            counts = {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in ("check_result", "check_cycle", "device_daily_failure", "offline_incident", "email_delivery")
            }
            for table in ("email_delivery", "device_daily_failure", "offline_incident", "check_result", "check_cycle"):
                connection.execute(f"DELETE FROM {table}")
            connection.execute(
                "INSERT INTO maintenance_audit(operation,started_at,completed_at,status,detail) VALUES('RESET',?,?, 'COMPLETED',?)",
                (current_timestamp(), current_timestamp(), str(counts)),
            )
        return counts

    def compact(self) -> dict[str, object]:
        context = self.activity_gate.exclusive("COMPACT") if self.activity_gate else _null_context()
        with context:
            database = self.repository.database_path.resolve()
            backup_root = self.monitoring_root / "backup"
            backup_root.mkdir(parents=True, exist_ok=True)
            backup = backup_root / f"finger_monitoring.pre-compact.{uuid.uuid4().hex}.bak"
            self._backup(database, backup)
            try:
                with self.repository.factory.connect(database) as connection:
                    connection.execute("VACUUM")
                self.repository.add_maintenance_audit(
                    "COMPACT", "COMPLETED", backup_path=str(backup),
                    detail=f"size_bytes={database.stat().st_size}",
                )
            except Exception:
                # The verified backup remains available; SQLite VACUUM is atomic.
                raise
        return {"backup_path": backup, "size_bytes": database.stat().st_size}

    @staticmethod
    def _backup(source: Path, destination: Path) -> None:
        try:
            # Fail quickly before sqlite3.backup(), whose internal BUSY handling
            # may otherwise wait repeatedly on an externally held writer lock.
            with closing(sqlite3.connect(source, timeout=0.5)) as probe:
                probe.execute("PRAGMA busy_timeout=500")
                probe.execute("BEGIN IMMEDIATE")
                probe.rollback()
            with closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as source_connection:
                with closing(sqlite3.connect(destination)) as target:
                    source_connection.backup(target)
                    target.commit()
                    integrity = target.execute("PRAGMA integrity_check").fetchone()
                    if integrity is None or integrity[0] != "ok":
                        raise sqlite3.DatabaseError("Backup integrity check gagal.")
        except Exception:
            if destination.exists():
                destination.unlink()
            raise

    @staticmethod
    def _revision(connection) -> tuple[int, int, int, int]:
        result = connection.execute("SELECT COUNT(*),COALESCE(MAX(result_id),0) FROM check_result").fetchone()
        cycle = connection.execute("SELECT COUNT(*),COALESCE(MAX(cycle_id),0) FROM check_cycle").fetchone()
        return int(result[0]), int(result[1]), int(cycle[0]), int(cycle[1])


from contextlib import contextmanager


@contextmanager
def _null_context():
    yield
