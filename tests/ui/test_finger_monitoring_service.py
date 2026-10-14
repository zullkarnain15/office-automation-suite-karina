"""Non-GUI integration tests for the Finger Monitoring UI facade."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ui.page_registry import build_default_page_registry
from ui.services.finger_monitoring_service import FingerMonitoringService


@dataclass
class _Status:
    data_root: Path


class _Storage:
    def __init__(self, root): self.root = root
    def resolve_status(self): return _Status(self.root)


def test_service_reads_paginated_status_history_and_settings(tmp_path):
    service = FingerMonitoringService(_Storage(tmp_path))
    service.initialize()
    device = service.device_master.add_device("Jakarta", "10.70.0.1")
    for status in ("ONLINE", "OFFLINE", "NETWORK_UNREACHABLE"):
        cycle = service.repository.create_cycle("CHECK_ALL", 1)
        service.repository.persist_check_outcome(cycle, device, status, observed_date="2026-10-12")
        service.repository.complete_cycle(cycle)
    assert service.dashboard()["total"] == 1
    assert service.device_status(status="OFFLINE") == ()
    assert service.device_status(status="NETWORK_UNREACHABLE")[0]["device_id"] == device
    history = service.history(limit=2, offset=0)
    assert history["total"] == 3 and len(history["items"]) == 2
    assert service.save_settings(auto_check_interval_hours=3)["auto_check_interval_hours"] == 3


def test_history_supports_whitelisted_sorting(tmp_path):
    service = FingerMonitoringService(_Storage(tmp_path))
    service.initialize()
    zulu = service.device_master.add_device("Zulu", "10.70.0.2")
    alpha = service.device_master.add_device("Alpha", "10.70.0.1")
    cycle = service.repository.create_cycle("CHECK_ALL", 2)
    service.repository.persist_check_outcome(
        cycle, zulu, "ONLINE", observed_date="2026-10-12"
    )
    service.repository.persist_check_outcome(
        cycle, alpha, "OFFLINE", observed_date="2026-10-12"
    )
    service.repository.complete_cycle(cycle)

    rows = service.history(sort_by="branch_name", descending=False)["items"]
    assert [row["branch_name"] for row in rows] == ["Alpha", "Zulu"]


def test_service_follows_changed_data_root_and_registry_has_page(tmp_path):
    storage = _Storage(tmp_path / "first")
    service = FingerMonitoringService(storage)
    first = service.initialize().database_path
    storage.root = tmp_path / "second"
    second = service.initialize().database_path
    assert first != second and second.is_file()
    assert "finger_monitoring" in build_default_page_registry().page_ids
