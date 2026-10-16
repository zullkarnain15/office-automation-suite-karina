"""UI-facing facade for the isolated Finger Monitoring module."""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from openpyxl import Workbook

from shared.finger_monitoring import (
    DeviceMasterService,
    FingerMonitoringRepository,
    FingerMonitoringStorageService,
    MonitoringCoordinator,
)
from shared.finger_monitoring.activity import FingerMonitoringActivityGate
from shared.finger_monitoring.email_service import DailyEmailReportService
from shared.finger_monitoring.maintenance_service import FingerMonitoringMaintenanceService
from shared.finger_monitoring.mdb_backup_service import MDBBackupMonitoringService


class FingerMonitoringService:
    """Lazily resolves the current Data Root; importing it creates no database."""

    def __init__(self, core_storage_service) -> None:
        self.storage = FingerMonitoringStorageService(core_storage_service)
        self._repository = None
        self._database_path: Path | None = None
        self._coordinator = None
        self._email_service = None
        self._activity_gate = FingerMonitoringActivityGate()
        self._initialization_lock = RLock()
        self.backup_monitoring = MDBBackupMonitoringService(core_storage_service)

    def initialize(self):
        with self._initialization_lock:
            status = self.storage.initialize()
            path = Path(status.database_path)
            if self._database_path != path:
                self.stop()
                self._repository = FingerMonitoringRepository(path)
                self._database_path = path
            if self._email_service is None:
                self._email_service = DailyEmailReportService(
                    self._repository, activity_gate=self._activity_gate
                )
            return status

    @property
    def repository(self):
        with self._initialization_lock:
            root = self.storage.selected_data_root()
            path = self.storage.database_path(root)
            if self._repository is None or path != self._database_path:
                self.initialize()
            return self._repository

    @property
    def device_master(self):
        return DeviceMasterService(self.repository, activity_gate=self._activity_gate)

    @property
    def maintenance(self):
        status = self.initialize()
        return FingerMonitoringMaintenanceService(
            self._repository,
            status.monitoring_root,
            activity_gate=self._activity_gate,
        )

    def start(self) -> bool:
        self.initialize()
        if self._coordinator is None:
            self._coordinator = MonitoringCoordinator(
                self._repository,
                activity_gate=self._activity_gate,
                cycle_completed_callback=self._email_service.consider_cycle,
            )
        return self._coordinator.start()

    def stop(self) -> None:
        if self._coordinator is not None:
            self._coordinator.stop()
            self._coordinator = None
        if self._email_service is not None:
            self._email_service.shutdown()
            self._email_service = None

    def coordinator_status(self):
        return self._coordinator.get_status() if self._coordinator else {"running": False, "cycle_active": False}

    def check_all(self) -> bool:
        return bool(self._coordinator and self._coordinator.check_all())

    def check_selected(self, device_ids) -> bool:
        return bool(self._coordinator and self._coordinator.check_selected(device_ids))

    def cancel_current_cycle(self) -> bool:
        return bool(self._coordinator and self._coordinator.cancel_current_cycle())

    def drain_events(self):
        return self._coordinator.drain_events() if self._coordinator else ()

    def settings(self):
        return self.repository.get_settings()

    def save_settings(self, **values):
        return self.repository.update_settings(**values)

    def backup_monitoring_settings(self):
        settings = self.settings()
        return {
            "root": str(settings["backup_mdb_root"]),
            "exclusions": str(settings["backup_mdb_exclusions"]),
        }

    def save_backup_monitoring_settings(self, root, exclusions):
        settings = self.save_settings(
            backup_mdb_root=str(root).strip(),
            backup_mdb_exclusions=str(exclusions).strip(),
        )
        return {
            "root": str(settings["backup_mdb_root"]),
            "exclusions": str(settings["backup_mdb_exclusions"]),
        }

    def latest_email_delivery(self):
        return self.repository.latest_email_delivery()

    def retry_daily_email(self) -> bool:
        if self._email_service is None:
            self.initialize()
        latest = self.repository.latest_email_delivery()
        if not latest or latest["status"] != "FAILED":
            return False
        return self._email_service.retry_failed(str(latest["report_date"]))

    def device_status(self, *, search="", device_model=None, status=None):
        repo = self.repository
        devices = repo.list_devices(search=search, device_model=device_model)
        if not devices:
            return ()
        ids = tuple(row["device_id"] for row in devices)
        marks = ",".join("?" for _ in ids)
        with repo.factory.connect(repo.database_path, read_only=True) as connection:
            rows = connection.execute(
                f"""SELECT d.device_id,d.unit,d.three_lc,d.branch_name,d.ip_address,d.device_model,d.note,
                    COALESCE((SELECT r.status FROM check_result r WHERE r.device_id=d.device_id ORDER BY r.checked_at DESC,r.result_id DESC LIMIT 1),'UNKNOWN') AS status,
                    (SELECT MAX(r.checked_at) FROM check_result r WHERE r.device_id=d.device_id AND r.status='ONLINE') AS last_online,
                    (SELECT COUNT(*) FROM device_daily_failure f WHERE f.device_id=d.device_id) AS offline_days
                    FROM device_master d WHERE d.device_id IN ({marks}) ORDER BY d.branch_name,d.ip_address""",
                ids,
            ).fetchall()
        result = tuple(dict(row) for row in rows)
        return tuple(row for row in result if status in (None, "", "ALL") or row["status"] == status)

    def dashboard(self):
        rows = self.device_status()
        return self._dashboard_from_rows(rows)

    def _dashboard_from_rows(self, rows):
        threshold = int(self.settings()["offline_alert_observed_dates"])
        return {
            "total": len(rows),
            "online": sum(row["status"] == "ONLINE" for row in rows),
            "offline": sum(row["status"] == "OFFLINE" for row in rows),
            "alert": sum(int(row["offline_days"]) >= threshold for row in rows),
        }

    def status_snapshot(self, *, search="", device_model=None, status=None):
        """Read all active statuses once for the KPIs and filtered table."""
        rows = self.device_status()
        dashboard = self._dashboard_from_rows(rows)
        token = search.strip().casefold()
        visible = tuple(
            row for row in rows
            if (not token or token in row["branch_name"].casefold() or token in row["ip_address"].casefold())
            and (not device_model or row["device_model"] == device_model)
            and (status in (None, "", "ALL") or row["status"] == status)
        )
        return dashboard, visible

    def history(
        self,
        *,
        date_from="",
        date_to="",
        branch="",
        status="",
        limit=100,
        offset=0,
        sort_by="checked_at",
        descending=True,
    ):
        repo = self.repository
        clauses, args = ["1=1"], []
        if date_from: clauses.append("substr(r.checked_at,1,10)>=?"); args.append(date_from)
        if date_to: clauses.append("substr(r.checked_at,1,10)<=?"); args.append(date_to)
        if branch: clauses.append("d.branch_name LIKE ? COLLATE NOCASE"); args.append(f"%{branch}%")
        if status: clauses.append("r.status=?"); args.append(status)
        where = " AND ".join(clauses)
        order_columns = {
            "checked_at": "r.checked_at",
            "unit": "d.unit COLLATE NOCASE",
            "three_lc": "d.three_lc COLLATE NOCASE",
            "branch_name": "d.branch_name COLLATE NOCASE",
            "ip_address": "d.ip_address",
            "device_model": "d.device_model",
            "status": "r.status",
            "latency_ms": "r.latency_ms",
            "diagnostic": "r.diagnostic COLLATE NOCASE",
        }
        if sort_by not in order_columns:
            raise ValueError("Kolom history untuk sort tidak valid.")
        direction = "DESC" if descending else "ASC"
        order_by = f"{order_columns[sort_by]} {direction}, r.result_id {direction}"
        with repo.factory.connect(repo.database_path, read_only=True) as connection:
            total = int(connection.execute(f"SELECT COUNT(*) FROM check_result r JOIN device_master d ON d.device_id=r.device_id WHERE {where}", args).fetchone()[0])
            items = tuple(dict(row) for row in connection.execute(
                f"""SELECT r.result_id,r.checked_at,d.unit,d.three_lc,d.branch_name,d.ip_address,d.device_model,r.status,r.latency_ms,r.diagnostic
                    FROM check_result r JOIN device_master d ON d.device_id=r.device_id WHERE {where}
                    ORDER BY {order_by} LIMIT ? OFFSET ?""",
                (*args, int(limit), int(offset)),
            ))
        return {"total": total, "items": items}

    def export_history(self, path, **filters):
        """Stream bounded history pages into an Excel workbook without GUI calls."""
        from shared.finger_monitoring.device_master_service import DeviceMasterService
        target = Path(path)
        if target.suffix.lower() != ".xlsx":
            raise ValueError("Export harus berformat .xlsx.")
        workbook = Workbook(); sheet = workbook.active; sheet.title = "History"
        headers = ("Checked_At", "Unit", "3LC", "Branch_Name", "IP_Address", "Device_Model", "Status", "Latency_ms", "Diagnostic")
        sheet.append(headers)
        offset = 0
        while True:
            page = self.history(limit=1000, offset=offset, **filters)
            for row in page["items"]:
                sheet.append(tuple(row[key] for key in ("checked_at", "unit", "three_lc", "branch_name", "ip_address", "device_model", "status", "latency_ms", "diagnostic")))
            offset += len(page["items"])
            if offset >= page["total"]: break
        for column, width in enumerate((20, 14, 14, 28, 18, 14, 24, 12, 55), 1): sheet.column_dimensions[chr(64 + column)].width = width
        DeviceMasterService._atomic_save(workbook, target)
        return target
