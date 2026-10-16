"""Sprint 2 contract tests for isolated Finger Monitoring persistence."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from shared.finger_monitoring import (
    FINGER_MONITORING_SCHEMA_VERSION,
    FingerMonitoringRepository,
    FingerMonitoringStorageService,
)


@dataclass
class _Status:
    data_root: Path


class _CoreStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def resolve_status(self):
        return _Status(self.root)


def _initialized(tmp_path):
    storage = FingerMonitoringStorageService(_CoreStorage(tmp_path))
    status = storage.initialize()
    return storage, status, FingerMonitoringRepository(status.database_path)


def test_initialize_creates_isolated_database_and_defaults(tmp_path):
    storage, status, repository = _initialized(tmp_path)
    assert status.database_path == tmp_path / "monitoring" / "finger" / "database" / "finger_monitoring.db"
    assert status.database_path.is_file()
    assert (tmp_path / "monitoring" / "finger" / "backup").is_dir()
    assert (tmp_path / "monitoring" / "finger" / "export").is_dir()
    assert (tmp_path / "monitoring" / "finger" / "logs").is_dir()
    assert repository.status()["schema_version"] == FINGER_MONITORING_SCHEMA_VERSION
    assert repository.get_settings()["ping_timeout_ms"] == 1500
    assert repository.get_settings()["max_workers"] == 5
    assert repository.get_settings()["backup_mdb_root"] == ""
    assert repository.get_settings()["backup_mdb_exclusions"] == "arsip*;archive*"
    assert storage.resolve_status().database_valid


def test_initialize_is_idempotent_and_preserves_data(tmp_path):
    storage, _status, repository = _initialized(tmp_path)
    device_id = repository.create_device("Jakarta", "10.0.0.1", device_model="X1800")
    again = storage.initialize()
    assert again.database_valid
    assert [row["device_id"] for row in repository.list_devices()] == [device_id]


def test_backup_mdb_settings_persist_when_repository_is_reopened(tmp_path):
    _storage, status, repository = _initialized(tmp_path)
    repository.update_settings(
        backup_mdb_root=r"\\server\backup\MDB",
        backup_mdb_exclusions="arsip*;archive*;old_*",
    )

    settings = FingerMonitoringRepository(status.database_path).get_settings()

    assert settings["backup_mdb_root"] == r"\\server\backup\MDB"
    assert settings["backup_mdb_exclusions"] == "arsip*;archive*;old_*"


def test_v5_migration_adds_backup_mdb_settings_without_losing_existing_settings(tmp_path):
    _storage, status, repository = _initialized(tmp_path)
    repository.update_settings(recipient_email="ops@example.test")
    with repository.factory.connect(status.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("ALTER TABLE monitoring_settings RENAME TO monitoring_settings_v6")
        connection.execute(
            """CREATE TABLE monitoring_settings (
                settings_id INTEGER PRIMARY KEY CHECK (settings_id = 1),
                recipient_email TEXT NOT NULL DEFAULT '',
                daily_report_start TEXT NOT NULL DEFAULT '07:00',
                auto_check_interval_hours INTEGER NOT NULL DEFAULT 2,
                ping_timeout_ms INTEGER NOT NULL DEFAULT 1500,
                max_workers INTEGER NOT NULL DEFAULT 5,
                offline_alert_observed_dates INTEGER NOT NULL DEFAULT 3,
                updated_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT INTO monitoring_settings
                SELECT settings_id,recipient_email,daily_report_start,
                       auto_check_interval_hours,ping_timeout_ms,max_workers,
                       offline_alert_observed_dates,updated_at
                FROM monitoring_settings_v6"""
        )
        connection.execute("DROP TABLE monitoring_settings_v6")
        connection.execute("UPDATE monitoring_metadata SET schema_version=5")
        connection.execute("PRAGMA user_version=5")

    assert repository.initialize() == FINGER_MONITORING_SCHEMA_VERSION
    settings = repository.get_settings()
    assert settings["recipient_email"] == "ops@example.test"
    assert settings["backup_mdb_root"] == ""
    assert settings["backup_mdb_exclusions"] == "arsip*;archive*"


def test_schema_constraints_and_rollback(tmp_path):
    _storage, status, repository = _initialized(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        with repository.factory.connect(status.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO device_master(branch_name,ip_address,created_at,updated_at) VALUES ('A','10.0.0.2','x','x')")
            connection.execute("INSERT INTO monitoring_settings(settings_id,updated_at) VALUES (2,'x')")
    with repository.factory.connect(status.database_path, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM device_master").fetchone()[0] == 0
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA user_version").fetchone()[0] == FINGER_MONITORING_SCHEMA_VERSION


def test_device_crud_soft_delete_and_reopen_persistence(tmp_path):
    _storage, status, repository = _initialized(tmp_path)
    device_id = repository.create_device("Bandung", "192.168.1.10")
    repository.update_device(device_id, "Bandung Barat", "192.168.1.11", device_model="X1800")
    assert repository.list_devices()[0]["device_model"] == "X1800"
    repository.soft_delete_device(device_id)
    assert repository.list_devices() == ()
    assert repository.list_devices(include_deleted=True)[0]["is_active"] == 0
    replacement = repository.create_device("Bandung Barat", "192.168.1.11")
    reopened = FingerMonitoringRepository(status.database_path)
    assert [row["device_id"] for row in reopened.list_devices()] == [replacement]


def test_cycle_observation_incident_email_and_settings(tmp_path):
    _storage, _status, repository = _initialized(tmp_path)
    device = repository.create_device("Surabaya", "172.16.0.10")
    cycle = repository.create_cycle("CHECK_ALL", 1)
    repository.add_check_result(cycle, device, "OFFLINE")
    assert repository.observe_offline_date(device, "2026-10-12", cycle)
    assert not repository.observe_offline_date(device, "2026-10-12", cycle)
    incident = repository.open_or_update_incident(device, "2026-10-12", 3)
    assert repository.open_or_update_incident(device, "2026-10-12", 3) == incident
    delivery = repository.reserve_email_delivery("2026-10-12", cycle, "ops@example.test")
    repository.update_email_delivery(delivery, "SENT")
    settings = repository.update_settings(auto_check_interval_hours=3, recipient_email=" ops@example.test ")
    assert settings["auto_check_interval_hours"] == 3
    with pytest.raises(sqlite3.IntegrityError):
        repository.reserve_email_delivery("2026-10-12", cycle, "ops@example.test")
    repository.resolve_incident_and_failures(device)
    with repository.factory.connect(repository.database_path, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM device_daily_failure").fetchone()[0] == 0


def test_corrupt_database_is_not_overwritten(tmp_path):
    root = tmp_path
    database = root / "monitoring" / "finger" / "database" / "finger_monitoring.db"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"not a sqlite database")
    storage = FingerMonitoringStorageService(_CoreStorage(root))
    original = database.read_bytes()
    with pytest.raises(sqlite3.DatabaseError):
        storage.initialize()
    assert database.read_bytes() == original


def test_locked_database_fails_safely(tmp_path):
    _storage, status, _repository = _initialized(tmp_path)
    locker = sqlite3.connect(status.database_path, timeout=0)
    try:
        locker.execute("BEGIN EXCLUSIVE")
        with pytest.raises(sqlite3.OperationalError):
            FingerMonitoringRepository(status.database_path).create_device("Lock", "10.0.0.9")
    finally:
        locker.rollback()
        locker.close()


def test_import_has_no_database_side_effect(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import shared.finger_monitoring  # noqa: F401

    assert not tuple(tmp_path.rglob("finger_monitoring.db"))
