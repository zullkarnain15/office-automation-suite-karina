"""Transactional repository for Finger Monitoring persistence only."""

from __future__ import annotations

import ipaddress
import sqlite3
from pathlib import Path
from typing import Any

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.time_utils import current_timestamp
from shared.finger_monitoring.schema import FingerMonitoringSchemaManager


class FingerMonitoringRepository:
    """Short-lived transactional access; it never runs checks or sends mail."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.factory = SQLiteConnectionFactory()
        self.schema_manager = FingerMonitoringSchemaManager(self.factory)

    def initialize(self) -> int:
        return self.schema_manager.initialize(self.database_path)

    def status(self) -> dict[str, Any]:
        version = self.schema_manager.validate(self.database_path)
        return {"database_path": self.database_path, "schema_version": version}

    def list_devices(
        self,
        *,
        include_deleted: bool = False,
        search: str = "",
        device_model: str | None = None,
        active: bool | None = None,
    ) -> tuple[dict[str, Any], ...]:
        """Search device master without exposing deleted records by default."""
        sql = "SELECT * FROM device_master"
        clauses, arguments = [], []
        if not include_deleted and active is None:
            active = True
        if active is not None:
            clauses.append("is_active=?")
            arguments.append(int(active))
        if device_model:
            clauses.append("device_model=?")
            arguments.append(device_model.strip().upper())
        if search.strip():
            clauses.append("(branch_name LIKE ? COLLATE NOCASE OR ip_address LIKE ?)")
            token = f"%{search.strip()}%"
            arguments.extend((token, token))
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY branch_name, ip_address, device_id"
        return self._read_rows(sql, tuple(arguments))

    def list_active_devices_by_ids(self, device_ids) -> tuple[dict[str, Any], ...]:
        """Return active devices in caller order, ignoring unknown/deleted IDs."""
        ids = tuple(dict.fromkeys(int(item) for item in device_ids))
        if not ids:
            return ()
        placeholders = ",".join("?" for _ in ids)
        found = self._read_rows(
            f"SELECT * FROM device_master WHERE is_active=1 AND device_id IN ({placeholders})",
            ids,
        )
        by_id = {row["device_id"]: row for row in found}
        return tuple(by_id[item] for item in ids if item in by_id)

    def create_device(
        self,
        branch_name: str,
        ip_address: str,
        *,
        device_model: str = "X1500",
        unit: str = "",
        three_lc: str = "",
        note: str = "",
    ) -> int:
        branch, address, model = self._device_values(branch_name, ip_address, device_model)
        unit, three_lc, note = self._additional_values(unit, three_lc, note)
        now = current_timestamp()
        def write(connection):
            self._ensure_active_ip_available(connection, address)
            return self._insert_device(
                connection, unit, three_lc, branch, address, model, note, now
            )
        return self._write(write)

    @staticmethod
    def _insert_device(
        connection,
        unit: str,
        three_lc: str,
        branch: str,
        address: str,
        model: str,
        note: str,
        now: str,
    ) -> int:
        cursor = connection.execute(
            "INSERT INTO device_master(unit,three_lc,branch_name,ip_address,device_model,note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (unit, three_lc, branch, address, model, note, now, now),
        )
        return int(cursor.lastrowid)

    def update_device(
        self,
        device_id: int,
        branch_name: str,
        ip_address: str,
        *,
        device_model: str = "X1500",
        unit: str | None = None,
        three_lc: str | None = None,
        note: str | None = None,
    ) -> None:
        branch, address, model = self._device_values(branch_name, ip_address, device_model)
        unit = None if unit is None else str(unit).strip()
        three_lc = None if three_lc is None else str(three_lc).strip()
        note = None if note is None else str(note).strip()
        now = current_timestamp()
        def write(connection):
            self._ensure_active_ip_available(connection, address, except_device_id=int(device_id))
            changed = connection.execute(
                "UPDATE device_master SET unit=COALESCE(?,unit),three_lc=COALESCE(?,three_lc),branch_name=?,ip_address=?,device_model=?,note=COALESCE(?,note),updated_at=? WHERE device_id=? AND is_active=1",
                (unit, three_lc, branch, address, model, note, now, int(device_id)),
            ).rowcount
            if changed != 1:
                raise KeyError("Perangkat aktif tidak ditemukan.")
        self._write(write)

    @staticmethod
    def _additional_values(unit: str, three_lc: str, note: str) -> tuple[str, str, str]:
        return (
            str(unit or "").strip(),
            str(three_lc or "").strip(),
            str(note or "").strip(),
        )

    def soft_delete_device(self, device_id: int) -> None:
        now = current_timestamp()
        def write(connection):
            changed = connection.execute(
                "UPDATE device_master SET is_active=0,deleted_at=?,updated_at=? WHERE device_id=? AND is_active=1",
                (now, now, int(device_id)),
            ).rowcount
            if changed != 1:
                raise KeyError("Perangkat aktif tidak ditemukan.")
        self._write(write)

    def reactivate_device(self, device_id: int) -> None:
        """Reactivate a soft-deleted device if its IP is globally available."""
        now = current_timestamp()
        def write(connection):
            row = connection.execute(
                "SELECT ip_address FROM device_master WHERE device_id=? AND is_active=0",
                (int(device_id),),
            ).fetchone()
            if row is None:
                raise KeyError("Perangkat nonaktif tidak ditemukan.")
            conflict = connection.execute(
                "SELECT device_id FROM device_master WHERE ip_address=? AND is_active=1",
                (row[0],),
            ).fetchone()
            if conflict is not None:
                raise ValueError("IP_Address sudah dipakai perangkat aktif lain.")
            self._require_one(connection.execute(
                "UPDATE device_master SET is_active=1,deleted_at=NULL,updated_at=? WHERE device_id=?",
                (now, int(device_id)),
            ).rowcount, "Perangkat nonaktif tidak ditemukan.")
        self._write(write)

    def device_revision(self) -> tuple[int, int, str | None]:
        """Small optimistic-concurrency token for import preview/commit."""
        with self.factory.connect(self.database_path, read_only=True) as connection:
            return self._device_revision(connection)

    def get_settings(self) -> dict[str, Any]:
        rows = self._read_rows("SELECT * FROM monitoring_settings WHERE settings_id=1")
        if not rows:
            raise sqlite3.DatabaseError("Monitoring settings tidak ditemukan.")
        return rows[0]

    def update_settings(self, **values: Any) -> dict[str, Any]:
        allowed = {
            "recipient_email", "daily_report_start", "auto_check_interval_hours",
            "ping_timeout_ms", "max_workers", "offline_alert_observed_dates",
        }
        unknown = set(values) - allowed
        if unknown:
            raise ValueError("Setting tidak dikenal: " + ", ".join(sorted(unknown)))
        if not values:
            return self.get_settings()
        values = dict(values)
        if "recipient_email" in values:
            values["recipient_email"] = str(values["recipient_email"]).strip()
        if "daily_report_start" in values:
            value = str(values["daily_report_start"])
            if len(value) != 5 or value[2] != ":" or not value.replace(":", "").isdigit() or not (0 <= int(value[:2]) <= 23 and 0 <= int(value[3:]) <= 59):
                raise ValueError("daily_report_start harus HH:MM.")
        fields = [f"{name}=?" for name in values]
        arguments = [values[name] for name in values]
        fields.append("updated_at=?")
        arguments.append(current_timestamp())
        self._write(lambda c: c.execute("UPDATE monitoring_settings SET " + ", ".join(fields) + " WHERE settings_id=1", arguments))
        return self.get_settings()

    def create_cycle(self, trigger_source: str, requested_devices: int, *, started_at: str | None = None) -> int:
        if trigger_source not in {"AUTO", "CHECK_ALL", "CHECK_SELECTED"} or requested_devices < 0:
            raise ValueError("Cycle tidak valid.")
        return self._write(lambda c: int(c.execute(
            "INSERT INTO check_cycle(trigger_source,started_at,requested_devices) VALUES(?,?,?)",
            (trigger_source, started_at or current_timestamp(), requested_devices),
        ).lastrowid))

    def complete_cycle(self, cycle_id: int, status: str = "COMPLETED", *, error_detail: str | None = None, completed_at: str | None = None) -> None:
        if status not in {"COMPLETED", "CANCELLED", "FAILED"}:
            raise ValueError("Status cycle tidak valid.")
        self._write(lambda c: self._require_one(c.execute(
            "UPDATE check_cycle SET status=?,completed_at=?,error_detail=? WHERE cycle_id=? AND status='RUNNING'",
            (status, completed_at or current_timestamp(), error_detail, int(cycle_id)),
        ).rowcount, "Cycle RUNNING tidak ditemukan."))

    def add_check_result(self, cycle_id: int, device_id: int, status: str, *, latency_ms: int | None = None, exit_code: int | None = None, diagnostic: str | None = None, checked_at: str | None = None) -> int:
        allowed = {"ONLINE", "OFFLINE", "NETWORK_UNREACHABLE", "UNKNOWN", "ERROR", "CANCELLED"}
        if status not in allowed or latency_ms is not None and latency_ms < 0:
            raise ValueError("Hasil pemeriksaan tidak valid.")
        return self._write(lambda c: int(c.execute(
            "INSERT INTO check_result(cycle_id,device_id,checked_at,status,latency_ms,exit_code,diagnostic) VALUES(?,?,?,?,?,?,?)",
            (int(cycle_id), int(device_id), checked_at or current_timestamp(), status, latency_ms, exit_code, diagnostic),
        ).lastrowid))

    def persist_check_outcome(
        self,
        cycle_id: int,
        device_id: int,
        status: str,
        *,
        latency_ms: int | None = None,
        exit_code: int | None = None,
        diagnostic: str | None = None,
        checked_at: str | None = None,
        observed_date: str | None = None,
        alert_threshold: int = 3,
    ) -> dict[str, Any]:
        """Persist one result and its offline state transition atomically."""
        allowed = {"ONLINE", "OFFLINE", "NETWORK_UNREACHABLE", "UNKNOWN", "ERROR", "CANCELLED"}
        if status not in allowed or latency_ms is not None and latency_ms < 0:
            raise ValueError("Hasil pemeriksaan tidak valid.")
        if alert_threshold < 1:
            raise ValueError("Alert threshold harus positif.")
        checked = checked_at or current_timestamp()

        def write(c):
            result_id = int(c.execute(
                "INSERT INTO check_result(cycle_id,device_id,checked_at,status,latency_ms,exit_code,diagnostic) VALUES(?,?,?,?,?,?,?)",
                (int(cycle_id), int(device_id), checked, status, latency_ms, exit_code, diagnostic),
            ).lastrowid)
            if status == "ONLINE":
                c.execute("UPDATE offline_incident SET resolved_at=?,resolution='ONLINE' WHERE device_id=? AND resolved_at IS NULL", (checked, int(device_id)))
                c.execute("DELETE FROM device_daily_failure WHERE device_id=?", (int(device_id),))
                return {"result_id": result_id, "offline_dates": 0, "alert": False}
            if status != "OFFLINE":
                return {"result_id": result_id, "offline_dates": self._failure_count(c, device_id), "alert": False}
            if not observed_date:
                raise ValueError("observed_date wajib untuk status OFFLINE.")
            row = c.execute("SELECT 1 FROM device_daily_failure WHERE device_id=? AND observed_date=?", (int(device_id), observed_date)).fetchone()
            if row:
                c.execute("UPDATE device_daily_failure SET last_cycle_id=?,observed_at=? WHERE device_id=? AND observed_date=?", (int(cycle_id), checked, int(device_id), observed_date))
            else:
                c.execute("INSERT INTO device_daily_failure(device_id,observed_date,first_cycle_id,last_cycle_id,observed_at) VALUES(?,?,?,?,?)", (int(device_id), observed_date, int(cycle_id), int(cycle_id), checked))
            count = self._failure_count(c, device_id)
            c.execute(
                "UPDATE check_result SET offline_observed_days=? WHERE result_id=?",
                (count, result_id),
            )
            alert = count >= alert_threshold
            if alert:
                active = c.execute("SELECT incident_id FROM offline_incident WHERE device_id=? AND resolved_at IS NULL", (int(device_id),)).fetchone()
                if active is None:
                    first_date = c.execute("SELECT MIN(observed_date) FROM device_daily_failure WHERE device_id=?", (int(device_id),)).fetchone()[0]
                    c.execute("INSERT INTO offline_incident(device_id,opened_at,first_failure_date,alert_threshold,alert_reached_at) VALUES(?,?,?,?,?)", (int(device_id), checked, first_date, alert_threshold, checked))
            return {"result_id": result_id, "offline_dates": count, "alert": alert}

        return self._write(write)

    def observe_offline_date(self, device_id: int, observed_date: str, cycle_id: int, *, observed_at: str | None = None) -> bool:
        """Persist one observation per date; returns true only when newly inserted."""
        now = observed_at or current_timestamp()
        def write(c):
            existing = c.execute("SELECT 1 FROM device_daily_failure WHERE device_id=? AND observed_date=?", (int(device_id), observed_date)).fetchone()
            if existing:
                c.execute("UPDATE device_daily_failure SET last_cycle_id=?,observed_at=? WHERE device_id=? AND observed_date=?", (int(cycle_id), now, int(device_id), observed_date))
                return False
            c.execute("INSERT INTO device_daily_failure(device_id,observed_date,first_cycle_id,last_cycle_id,observed_at) VALUES(?,?,?,?,?)", (int(device_id), observed_date, int(cycle_id), int(cycle_id), now))
            return True
        return bool(self._write(write))

    def open_or_update_incident(self, device_id: int, first_failure_date: str, alert_threshold: int, *, opened_at: str | None = None) -> int:
        if alert_threshold < 1:
            raise ValueError("Alert threshold harus positif.")
        def write(c):
            row = c.execute("SELECT incident_id FROM offline_incident WHERE device_id=? AND resolved_at IS NULL", (int(device_id),)).fetchone()
            if row:
                return int(row[0])
            return int(c.execute("INSERT INTO offline_incident(device_id,opened_at,first_failure_date,alert_threshold) VALUES(?,?,?,?)", (int(device_id), opened_at or current_timestamp(), first_failure_date, alert_threshold)).lastrowid)
        return self._write(write)

    def resolve_incident_and_failures(self, device_id: int, *, resolved_at: str | None = None) -> None:
        now = resolved_at or current_timestamp()
        def write(c):
            c.execute("UPDATE offline_incident SET resolved_at=?,resolution='ONLINE' WHERE device_id=? AND resolved_at IS NULL", (now, int(device_id)))
            c.execute("DELETE FROM device_daily_failure WHERE device_id=?", (int(device_id),))
        self._write(write)

    def reserve_email_delivery(self, report_date: str, cycle_id: int, recipient_email: str, *, reserved_at: str | None = None) -> int:
        return self._write(lambda c: int(c.execute(
            "INSERT INTO email_delivery(report_date,cycle_id,recipient_email,status,reserved_at) VALUES(?,?,?,'RESERVED',?)",
            (report_date, int(cycle_id), recipient_email.strip(), reserved_at or current_timestamp()),
        ).lastrowid))

    def reserve_failed_email_retry(
        self,
        report_date: str,
        cycle_id: int,
        recipient_email: str,
        *,
        reserved_at: str | None = None,
    ) -> int:
        """Atomically reserve one explicit retry of a failed daily delivery."""
        def write(connection):
            row = connection.execute(
                "SELECT delivery_id,status FROM email_delivery WHERE report_date=?",
                (report_date,),
            ).fetchone()
            if row is None or row["status"] != "FAILED":
                raise ValueError("Tidak ada email gagal yang dapat di-retry untuk tanggal ini.")
            connection.execute(
                "UPDATE email_delivery SET cycle_id=?,recipient_email=?,status='RESERVED',reserved_at=?,sent_at=NULL,error_detail=NULL WHERE delivery_id=?",
                (int(cycle_id), recipient_email.strip(), reserved_at or current_timestamp(), int(row["delivery_id"])),
            )
            return int(row["delivery_id"])
        return self._write(write)

    def email_delivery_for_date(self, report_date: str) -> dict[str, Any] | None:
        rows = self._read_rows(
            "SELECT * FROM email_delivery WHERE report_date=?", (report_date,)
        )
        return rows[0] if rows else None

    def latest_email_delivery(self) -> dict[str, Any] | None:
        rows = self._read_rows(
            "SELECT * FROM email_delivery ORDER BY report_date DESC,delivery_id DESC LIMIT 1"
        )
        return rows[0] if rows else None

    def update_email_delivery(self, delivery_id: int, status: str, *, attachment_path: str | None = None, error_detail: str | None = None, sent_at: str | None = None) -> None:
        if status not in {"SENT", "FAILED", "CANCELLED"}:
            raise ValueError("Status email tidak valid.")
        self._write(lambda c: self._require_one(c.execute(
            "UPDATE email_delivery SET status=?,sent_at=?,attachment_path=?,error_detail=? WHERE delivery_id=? AND status='RESERVED'",
            (status, sent_at or (current_timestamp() if status == "SENT" else None), attachment_path, error_detail, int(delivery_id)),
        ).rowcount, "Email reservation tidak ditemukan."))

    def add_maintenance_audit(self, operation: str, status: str, *, detail: str | None = None, backup_path: str | None = None, completed_at: str | None = None) -> int:
        if status not in {"STARTED", "COMPLETED", "FAILED"}:
            raise ValueError("Status maintenance tidak valid.")
        now = current_timestamp()
        return self._write(lambda c: int(c.execute(
            "INSERT INTO maintenance_audit(operation,started_at,completed_at,status,backup_path,detail) VALUES(?,?,?,?,?,?)",
            (operation, now, completed_at or (now if status != "STARTED" else None), status, backup_path, detail),
        ).lastrowid))

    def _read_rows(self, sql: str, arguments: tuple = ()) -> tuple[dict[str, Any], ...]:
        with self.factory.connect(self.database_path, read_only=True) as connection:
            return tuple(dict(row) for row in connection.execute(sql, arguments))

    @staticmethod
    def _failure_count(connection, device_id: int) -> int:
        return int(connection.execute(
            "SELECT COUNT(*) FROM device_daily_failure WHERE device_id=?", (int(device_id),)
        ).fetchone()[0])

    @staticmethod
    def _device_revision(connection) -> tuple[int, int, str | None]:
        row = connection.execute(
            "SELECT COUNT(*),COALESCE(MAX(device_id),0),MAX(updated_at) FROM device_master"
        ).fetchone()
        return (int(row[0]), int(row[1]), row[2])

    def _write(self, action):
        with self.factory.connect(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            return action(connection)

    @staticmethod
    def _require_one(rowcount: int, message: str) -> None:
        if rowcount != 1:
            raise KeyError(message)

    @staticmethod
    def _device_values(branch_name: str, ip_address: str, device_model: str) -> tuple[str, str, str]:
        branch, address, model = branch_name.strip(), ip_address.strip(), device_model.strip().upper()
        if not branch:
            raise ValueError("Branch_Name wajib diisi.")
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError("IP_Address tidak valid.") from exc
        if parsed.version != 4:
            raise ValueError("IP_Address saat ini harus IPv4.")
        if model not in {"X1500", "X1800"}:
            raise ValueError("Model perangkat harus X1500 atau X1800.")
        return branch, str(parsed), model

    @staticmethod
    def _ensure_active_ip_available(connection, address: str, *, except_device_id: int | None = None) -> None:
        sql = "SELECT device_id FROM device_master WHERE ip_address=? AND is_active=1"
        arguments: tuple[object, ...] = (address,)
        if except_device_id is not None:
            sql += " AND device_id<>?"
            arguments = (address, except_device_id)
        if connection.execute(sql, arguments).fetchone() is not None:
            raise ValueError("IP_Address sudah dipakai perangkat aktif lain.")
