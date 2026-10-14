"""Sprint 6 tests; Outlook and network are fully mocked."""

from __future__ import annotations

import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared.finger_monitoring import (
    FINGER_MONITORING_SCHEMA_VERSION,
    FingerMonitoringRepository,
    FingerMonitoringStorageService,
)
from shared.finger_monitoring.activity import FingerMonitoringActivityGate
from shared.finger_monitoring.email_service import DailyEmailReportService, JAKARTA
from shared.finger_monitoring.maintenance_service import FingerMonitoringMaintenanceService


@dataclass
class _Status:
    data_root: Path


class _Storage:
    def __init__(self, root): self.root = root
    def resolve_status(self): return _Status(self.root)


class _Sender:
    def __init__(self, error=None): self.error, self.messages = error, []
    def send_html(self, recipient, subject, body_html):
        if self.error: raise self.error
        self.messages.append((recipient, subject, body_html))


def _environment(tmp_path):
    storage = FingerMonitoringStorageService(_Storage(tmp_path)); status = storage.initialize()
    repo = FingerMonitoringRepository(status.database_path)
    repo.update_settings(recipient_email="ops@example.test", daily_report_start="07:00")
    return status, repo


def _cycle(repo, devices, statuses, *, source="CHECK_ALL", checked_at="2026-10-12T08:00:00"):
    cycle = repo.create_cycle(source, len(devices), started_at=checked_at)
    for device, status in zip(devices, statuses):
        repo.persist_check_outcome(cycle, device, status, checked_at=checked_at, observed_date=checked_at[:10])
    repo.complete_cycle(cycle, completed_at=checked_at)
    return cycle


def _wait_delivery(repo, report_date, expected, timeout=3):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        row = repo.email_delivery_for_date(report_date)
        if row and row["status"] == expected: return row
        time.sleep(0.01)
    raise AssertionError(f"delivery did not reach {expected}")


def test_daily_email_once_snapshot_html_and_no_selected(tmp_path):
    _status, repo = _environment(tmp_path)
    devices = (repo.create_device("Alert", "10.80.0.1"), repo.create_device("Unknown", "10.80.0.2"))
    # Establish three non-consecutive offline dates before the report cycle.
    for day in ("2026-10-01", "2026-10-03"):
        prior = _cycle(repo, devices[:1], ("OFFLINE",), checked_at=f"{day}T08:00:00")
    report_cycle = _cycle(repo, devices, ("OFFLINE", "ERROR"))
    sender = _Sender(); service = DailyEmailReportService(repo, sender=sender, now=lambda: datetime(2026, 10, 12, 8, tzinfo=JAKARTA))
    assert service.consider_cycle(report_cycle, "CHECK_ALL", "COMPLETED")
    _wait_delivery(repo, "2026-10-12", "SENT")
    assert not service.consider_cycle(report_cycle, "CHECK_ALL", "COMPLETED")
    assert len(sender.messages) == 1
    recipient, subject, body = sender.messages[0]
    assert recipient == "ops@example.test"
    assert subject == "[OAS-K] Finger Monitoring - 1 Devices Offline"
    assert "<td>Alert</td>" in body and "<td>Unknown</td>" not in body and "could not be verified" in body
    assert "<th>Observed Offline Days</th>" in body
    selected = _cycle(repo, devices[:1], ("ONLINE",), source="CHECK_SELECTED")
    assert not service.consider_cycle(selected, "CHECK_SELECTED", "COMPLETED")
    service.shutdown()


def test_all_online_incomplete_cancelled_and_before_start_do_not_send(tmp_path):
    _status, repo = _environment(tmp_path); device = repo.create_device("A", "10.81.0.1")
    cycle = _cycle(repo, (device,), ("ONLINE",))
    sender = _Sender(); before = DailyEmailReportService(repo, sender=sender, now=lambda: datetime(2026, 10, 12, 6, tzinfo=JAKARTA))
    assert not before.consider_cycle(cycle, "CHECK_ALL", "COMPLETED"); before.shutdown()
    incomplete = repo.create_cycle("CHECK_ALL", 2); repo.add_check_result(incomplete, device, "ONLINE"); repo.complete_cycle(incomplete)
    service = DailyEmailReportService(repo, sender=sender, now=lambda: datetime(2026, 10, 12, 8, tzinfo=JAKARTA))
    early_cycle = _cycle(repo, (device,), ("ONLINE",), checked_at="2026-10-12T06:59:00")
    assert not service.consider_cycle(early_cycle, "CHECK_ALL", "COMPLETED")
    assert not service.consider_cycle(incomplete, "CHECK_ALL", "COMPLETED")
    assert not service.consider_cycle(cycle, "CHECK_ALL", "CANCELLED")
    assert service.consider_cycle(cycle, "CHECK_ALL", "COMPLETED")
    _wait_delivery(repo, "2026-10-12", "SENT")
    assert "All Devices Online" in sender.messages[0][2]
    service.shutdown()


def test_outlook_failure_manual_retry_and_restart_deduplication(tmp_path):
    _status, repo = _environment(tmp_path); device = repo.create_device("A", "10.82.0.1")
    cycle = _cycle(repo, (device,), ("ONLINE",))
    now = lambda: datetime(2026, 10, 12, 8, tzinfo=JAKARTA)
    service = DailyEmailReportService(repo, sender=_Sender(RuntimeError("COM unavailable")), now=now)
    assert service.consider_cycle(cycle, "AUTO", "COMPLETED")
    failed = _wait_delivery(repo, "2026-10-12", "FAILED")
    assert "COM unavailable" in failed["error_detail"]
    sender = _Sender(); service.sender = sender
    assert service.retry_failed("2026-10-12")
    _wait_delivery(repo, "2026-10-12", "SENT")
    service.shutdown()
    restarted = DailyEmailReportService(repo, sender=_Sender(), now=now)
    assert not restarted.consider_cycle(cycle, "AUTO", "COMPLETED")
    restarted.shutdown()


def test_outlook_thread_initializes_com_and_records_security_error(tmp_path, monkeypatch):
    _status, repo = _environment(tmp_path); device = repo.create_device("A", "10.82.0.2")
    cycle = _cycle(repo, (device,), ("ONLINE",))
    calls = []
    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(
        CoInitialize=lambda: calls.append(("init", threading.get_ident())),
        CoUninitialize=lambda: calls.append(("uninit", threading.get_ident())),
    ))
    service = DailyEmailReportService(
        repo,
        sender=_Sender(PermissionError("Outlook security prompt blocked send")),
        now=lambda: datetime(2026, 10, 12, 8, tzinfo=JAKARTA),
    )
    assert service.consider_cycle(cycle, "CHECK_ALL", "COMPLETED")
    failed = _wait_delivery(repo, "2026-10-12", "FAILED")
    assert "security prompt" in failed["error_detail"]
    assert [name for name, _thread_id in calls] == ["init", "uninit"]
    assert calls[0][1] == calls[1][1] != threading.get_ident()
    service.shutdown()


@pytest.mark.parametrize("days", (30, 90, 180, None))
def test_cleanup_retention_preserves_incident_observations_and_email(tmp_path, days):
    status, repo = _environment(tmp_path); device = repo.create_device("A", "10.83.0.1")
    old = _cycle(repo, (device,), ("OFFLINE",), checked_at="2025-01-01T08:00:00")
    repo.open_or_update_incident(device, "2025-01-01", 3, opened_at="2025-01-01T08:00:00")
    repo.reserve_email_delivery("2025-01-01", old, "ops@example.test", reserved_at="2025-01-01T08:00:00")
    repo.update_email_delivery(1, "SENT", sent_at="2025-01-01T08:01:00")
    maintenance = FingerMonitoringMaintenanceService(repo, status.monitoring_root, now=lambda: datetime(2026, 10, 12))
    preview = maintenance.preview_cleanup(days)
    result = maintenance.cleanup(preview)
    assert result["deleted_results"] == 1
    with repo.factory.connect(repo.database_path, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM device_daily_failure").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM offline_incident WHERE resolved_at IS NULL").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM email_delivery").fetchone()[0] == 1


def test_reset_preserves_master_settings_and_compact_creates_valid_backup(tmp_path):
    status, repo = _environment(tmp_path); device = repo.create_device("A", "10.84.0.1")
    _cycle(repo, (device,), ("OFFLINE",))
    maintenance = FingerMonitoringMaintenanceService(repo, status.monitoring_root)
    with pytest.raises(ValueError): maintenance.reset_monitoring_data(confirmation="RESET")
    maintenance.reset_monitoring_data(confirmation="RESET MONITORING DATA")
    assert len(repo.list_devices()) == 1 and repo.get_settings()["recipient_email"] == "ops@example.test"
    with repo.factory.connect(repo.database_path, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM check_result").fetchone()[0] == 0
    compact = maintenance.compact()
    assert compact["backup_path"].is_file()
    with sqlite3.connect(compact["backup_path"]) as backup:
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_maintenance_gate_and_database_lock_fail_safely(tmp_path):
    status, repo = _environment(tmp_path); gate = FingerMonitoringActivityGate()
    maintenance = FingerMonitoringMaintenanceService(repo, status.monitoring_root, activity_gate=gate)
    with gate.activity("MONITORING"):
        with pytest.raises(RuntimeError): maintenance.preview_cleanup() if False else maintenance.compact()
    locker = sqlite3.connect(repo.database_path, timeout=0)
    try:
        locker.execute("BEGIN EXCLUSIVE")
        with pytest.raises(sqlite3.Error): maintenance.compact()
    finally:
        locker.rollback(); locker.close()
    assert repo.schema_manager.validate(repo.database_path) == FINGER_MONITORING_SCHEMA_VERSION
