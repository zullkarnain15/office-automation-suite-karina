"""Versioned SQLite schema for the dedicated Finger Monitoring database."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.time_utils import current_timestamp

FINGER_MONITORING_SCHEMA_VERSION = 4

REQUIRED_TABLES = frozenset(
    {
        "monitoring_metadata", "device_master", "monitoring_settings",
        "check_cycle", "check_result", "device_daily_failure",
        "offline_incident", "email_delivery", "maintenance_audit",
    }
)

SCHEMA_STATEMENTS = (
    """CREATE TABLE monitoring_metadata (
        metadata_id INTEGER PRIMARY KEY CHECK (metadata_id = 1),
        database_uuid TEXT NOT NULL UNIQUE,
        schema_version INTEGER NOT NULL CHECK (schema_version > 0),
        initialized_at TEXT NOT NULL, last_migrated_at TEXT
    )""",
    """CREATE TABLE device_master (
        device_id INTEGER PRIMARY KEY,
        unit TEXT NOT NULL DEFAULT '',
        three_lc TEXT NOT NULL DEFAULT '',
        branch_name TEXT NOT NULL COLLATE NOCASE CHECK (trim(branch_name) <> ''),
        ip_address TEXT NOT NULL COLLATE NOCASE CHECK (trim(ip_address) <> ''),
        device_model TEXT NOT NULL DEFAULT 'X1500'
            CHECK (device_model IN ('X1500', 'X1800')),
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
        note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT
    )""",
    "CREATE UNIQUE INDEX uq_device_master_active_ip ON device_master(ip_address) WHERE is_active = 1",
    "CREATE INDEX idx_device_master_active_branch ON device_master(is_active, branch_name)",
    """CREATE TABLE monitoring_settings (
        settings_id INTEGER PRIMARY KEY CHECK (settings_id = 1),
        recipient_email TEXT NOT NULL DEFAULT '',
        daily_report_start TEXT NOT NULL DEFAULT '07:00'
            CHECK (daily_report_start GLOB '[0-2][0-9]:[0-5][0-9]'),
        auto_check_interval_hours INTEGER NOT NULL DEFAULT 2 CHECK (auto_check_interval_hours IN (1, 2, 3)),
        ping_timeout_ms INTEGER NOT NULL DEFAULT 1500 CHECK (ping_timeout_ms BETWEEN 100 AND 60000),
        max_workers INTEGER NOT NULL DEFAULT 5 CHECK (max_workers BETWEEN 1 AND 5),
        offline_alert_observed_dates INTEGER NOT NULL DEFAULT 3 CHECK (offline_alert_observed_dates >= 1),
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE check_cycle (
        cycle_id INTEGER PRIMARY KEY,
        trigger_source TEXT NOT NULL CHECK (trigger_source IN ('AUTO', 'CHECK_ALL', 'CHECK_SELECTED')),
        started_at TEXT NOT NULL, completed_at TEXT,
        requested_devices INTEGER NOT NULL DEFAULT 0 CHECK (requested_devices >= 0),
        status TEXT NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING', 'COMPLETED', 'CANCELLED', 'FAILED')),
        error_detail TEXT
    )""",
    "CREATE INDEX idx_check_cycle_started_at ON check_cycle(started_at DESC)",
    """CREATE TABLE check_result (
        result_id INTEGER PRIMARY KEY, cycle_id INTEGER NOT NULL, device_id INTEGER NOT NULL,
        checked_at TEXT NOT NULL, status TEXT NOT NULL
            CHECK (status IN ('ONLINE', 'OFFLINE', 'NETWORK_UNREACHABLE', 'UNKNOWN', 'ERROR', 'CANCELLED')),
        latency_ms INTEGER CHECK (latency_ms >= 0), exit_code INTEGER,
        diagnostic TEXT,
        offline_observed_days INTEGER NOT NULL DEFAULT 0 CHECK (offline_observed_days >= 0),
        FOREIGN KEY (cycle_id) REFERENCES check_cycle(cycle_id) ON DELETE RESTRICT,
        FOREIGN KEY (device_id) REFERENCES device_master(device_id) ON DELETE RESTRICT,
        UNIQUE (cycle_id, device_id)
    )""",
    "CREATE INDEX idx_check_result_device_checked ON check_result(device_id, checked_at DESC)",
    "CREATE INDEX idx_check_result_cycle_status ON check_result(cycle_id, status)",
    """CREATE TABLE device_daily_failure (
        device_id INTEGER NOT NULL, observed_date TEXT NOT NULL,
        first_cycle_id INTEGER NOT NULL, last_cycle_id INTEGER NOT NULL,
        observed_at TEXT NOT NULL, PRIMARY KEY (device_id, observed_date),
        FOREIGN KEY (device_id) REFERENCES device_master(device_id) ON DELETE RESTRICT,
        FOREIGN KEY (first_cycle_id) REFERENCES check_cycle(cycle_id) ON DELETE RESTRICT,
        FOREIGN KEY (last_cycle_id) REFERENCES check_cycle(cycle_id) ON DELETE RESTRICT
    ) WITHOUT ROWID""",
    "CREATE INDEX idx_device_daily_failure_date ON device_daily_failure(observed_date DESC)",
    """CREATE TABLE offline_incident (
        incident_id INTEGER PRIMARY KEY, device_id INTEGER NOT NULL,
        opened_at TEXT NOT NULL, first_failure_date TEXT NOT NULL,
        alert_threshold INTEGER NOT NULL CHECK (alert_threshold >= 1),
        alert_reached_at TEXT, resolved_at TEXT, resolution TEXT,
        FOREIGN KEY (device_id) REFERENCES device_master(device_id) ON DELETE RESTRICT
    )""",
    "CREATE UNIQUE INDEX uq_offline_incident_active_device ON offline_incident(device_id) WHERE resolved_at IS NULL",
    "CREATE INDEX idx_offline_incident_active ON offline_incident(resolved_at, device_id)",
    """CREATE TABLE email_delivery (
        delivery_id INTEGER PRIMARY KEY, report_date TEXT NOT NULL,
        cycle_id INTEGER NOT NULL, recipient_email TEXT NOT NULL, status TEXT NOT NULL
            CHECK (status IN ('RESERVED', 'SENT', 'FAILED', 'CANCELLED')),
        reserved_at TEXT NOT NULL, sent_at TEXT, attachment_path TEXT, error_detail TEXT,
        FOREIGN KEY (cycle_id) REFERENCES check_cycle(cycle_id) ON DELETE RESTRICT,
        UNIQUE (report_date)
    )""",
    "CREATE INDEX idx_email_delivery_status_date ON email_delivery(status, report_date DESC)",
    """CREATE TABLE maintenance_audit (
        audit_id INTEGER PRIMARY KEY, operation TEXT NOT NULL,
        started_at TEXT NOT NULL, completed_at TEXT, status TEXT NOT NULL
            CHECK (status IN ('STARTED', 'COMPLETED', 'FAILED')),
        backup_path TEXT, detail TEXT
    )""",
    "CREATE INDEX idx_maintenance_audit_started ON maintenance_audit(started_at DESC)",
)


class FingerMonitoringSchemaManager:
    """Create and validate only the Finger Monitoring schema."""

    def __init__(self, factory: SQLiteConnectionFactory | None = None) -> None:
        self.factory = factory or SQLiteConnectionFactory()

    def initialize(self, database: str | Path) -> int:
        path = Path(database)
        if path.exists():
            return self.migrate_to_current(path)
        with self.factory.connect(path, create_parent=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            timestamp = current_timestamp()
            connection.execute(
                "INSERT INTO monitoring_metadata VALUES (1, ?, ?, ?, NULL)",
                (str(uuid.uuid4()), FINGER_MONITORING_SCHEMA_VERSION, timestamp),
            )
            connection.execute(
                "INSERT INTO monitoring_settings(settings_id, updated_at) VALUES (1, ?)",
                (timestamp,),
            )
            connection.execute(f"PRAGMA user_version = {FINGER_MONITORING_SCHEMA_VERSION}")
            connection.commit()
        self.validate(path)
        return FINGER_MONITORING_SCHEMA_VERSION

    def migrate_to_current(self, database: str | Path) -> int:
        """Apply controlled, sequential Finger Monitoring migrations."""
        path = Path(database)
        with self.factory.connect(path) as connection:
            metadata = connection.execute(
                "SELECT schema_version FROM monitoring_metadata WHERE metadata_id=1"
            ).fetchone()
            if metadata is None:
                raise sqlite3.DatabaseError("Finger Monitoring metadata is missing.")
            current = int(metadata[0])
            if current > FINGER_MONITORING_SCHEMA_VERSION:
                raise sqlite3.DatabaseError("Finger Monitoring schema is newer than this application.")
            if current == 1:
                # A v1 database may only be migrated when its existing active
                # records already comply with the new global-IP contract.
                duplicates = connection.execute(
                    "SELECT ip_address FROM device_master WHERE is_active=1 GROUP BY ip_address HAVING COUNT(*) > 1"
                ).fetchall()
                if duplicates:
                    raise sqlite3.DatabaseError(
                        "Migration requires resolving duplicate active IP addresses first."
                    )
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DROP INDEX IF EXISTS uq_device_master_active_branch_ip")
                connection.execute(
                    "CREATE UNIQUE INDEX uq_device_master_active_ip ON device_master(ip_address) WHERE is_active = 1"
                )
                timestamp = current_timestamp()
                connection.execute(
                    "UPDATE monitoring_metadata SET schema_version=?,last_migrated_at=? WHERE metadata_id=1",
                    (2, timestamp),
                )
                connection.execute("PRAGMA user_version = 2")
                connection.commit()
                current = 2
            if current == 2:
                connection.execute("BEGIN IMMEDIATE")
                columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(check_result)")
                }
                if "offline_observed_days" not in columns:
                    connection.execute(
                        "ALTER TABLE check_result ADD COLUMN offline_observed_days INTEGER NOT NULL DEFAULT 0 CHECK (offline_observed_days >= 0)"
                    )
                timestamp = current_timestamp()
                connection.execute(
                    "UPDATE monitoring_metadata SET schema_version=?,last_migrated_at=? WHERE metadata_id=1",
                    (3, timestamp),
                )
                connection.execute("PRAGMA user_version = 3")
                connection.commit()
                current = 3
            if current == 3:
                connection.execute("BEGIN IMMEDIATE")
                columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(device_master)")
                }
                for name in ("unit", "three_lc", "note"):
                    if name not in columns:
                        connection.execute(
                            f"ALTER TABLE device_master ADD COLUMN {name} TEXT NOT NULL DEFAULT ''"
                        )
                timestamp = current_timestamp()
                connection.execute(
                    "UPDATE monitoring_metadata SET schema_version=?,last_migrated_at=? WHERE metadata_id=1",
                    (4, timestamp),
                )
                connection.execute("PRAGMA user_version = 4")
                connection.commit()
                current = 4
            if current != FINGER_MONITORING_SCHEMA_VERSION:
                raise sqlite3.DatabaseError("No Finger Monitoring migration path is registered.")
        self.validate(path)
        return FINGER_MONITORING_SCHEMA_VERSION

    def validate(self, database: str | Path) -> int:
        path = Path(database)
        with self.factory.connect(path, read_only=True) as connection:
            tables = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing = REQUIRED_TABLES - tables
            if missing:
                raise sqlite3.DatabaseError("Finger Monitoring tables missing: " + ", ".join(sorted(missing)))
            metadata = connection.execute(
                "SELECT schema_version FROM monitoring_metadata WHERE metadata_id=1"
            ).fetchone()
            user_version = connection.execute("PRAGMA user_version").fetchone()
            if metadata is None or user_version is None:
                raise sqlite3.DatabaseError("Finger Monitoring metadata is missing.")
            version = int(metadata[0])
            if version != FINGER_MONITORING_SCHEMA_VERSION or int(user_version[0]) != version:
                raise sqlite3.DatabaseError("Finger Monitoring schema version is incompatible.")
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise sqlite3.DatabaseError("Finger Monitoring database integrity check failed.")
            return version
