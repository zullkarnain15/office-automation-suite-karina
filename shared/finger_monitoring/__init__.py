"""Isolated persistence foundation for the Finger Monitoring module.

Importing this package deliberately has no Data Root, database, GUI, worker,
or Outlook side effects.
"""

from shared.finger_monitoring.repository import FingerMonitoringRepository
from shared.finger_monitoring.coordinator import MonitoringCoordinator, MonitoringEvent
from shared.finger_monitoring.ping_engine import PingProbeResult, WindowsPingEngine
from shared.finger_monitoring.device_master_service import (
    DeviceImportPreview,
    DeviceMasterService,
)
from shared.finger_monitoring.email_service import DailyEmailReportService
from shared.finger_monitoring.maintenance_service import FingerMonitoringMaintenanceService
from shared.finger_monitoring.schema import FINGER_MONITORING_SCHEMA_VERSION
from shared.finger_monitoring.storage import (
    FingerMonitoringStorageService,
    FingerMonitoringStorageStatus,
)

__all__ = [
    "FINGER_MONITORING_SCHEMA_VERSION",
    "FingerMonitoringRepository",
    "FingerMonitoringStorageService",
    "FingerMonitoringStorageStatus",
    "MonitoringCoordinator",
    "MonitoringEvent",
    "PingProbeResult",
    "WindowsPingEngine",
    "DeviceImportPreview",
    "DeviceMasterService",
    "DailyEmailReportService",
    "FingerMonitoringMaintenanceService",
]
