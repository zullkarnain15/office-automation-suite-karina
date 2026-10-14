"""No-network tests for the bounded Finger Monitoring engine."""

from __future__ import annotations

import sqlite3
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest

from shared.finger_monitoring import (
    FingerMonitoringRepository, FingerMonitoringStorageService,
    MonitoringCoordinator, PingProbeResult, WindowsPingEngine,
)


@dataclass
class _Status:
    data_root: Path


class _Storage:
    def __init__(self, root): self.root = root
    def resolve_status(self): return _Status(self.root)


class _Timer:
    def __init__(self, seconds, callback, recorded):
        self.seconds, self.callback, self.recorded, self.cancelled = seconds, callback, recorded, False
    def start(self): self.recorded.append(self)
    def cancel(self): self.cancelled = True
    def fire(self):
        if not self.cancelled: self.callback()


class _Probe:
    def __init__(self, statuses=("ONLINE",), delay=0):
        self.statuses, self.delay = list(statuses), delay
        self.lock = threading.Lock()
        self.active = self.maximum = self.calls = 0
    def probe(self, ip, _timeout, cancel):
        with self.lock:
            self.active += 1; self.maximum = max(self.maximum, self.active); self.calls += 1
            status = self.statuses.pop(0) if self.statuses else "ONLINE"
        try:
            deadline = time.monotonic() + self.delay
            while time.monotonic() < deadline:
                if cancel.is_set(): return PingProbeResult("CANCELLED", ip, diagnostic="cancelled")
                time.sleep(0.005)
            return PingProbeResult(status, ip, latency_ms=7 if status == "ONLINE" else None)
        finally:
            with self.lock: self.active -= 1


def _repo(tmp_path):
    storage = FingerMonitoringStorageService(_Storage(tmp_path))
    status = storage.initialize()
    return FingerMonitoringRepository(status.database_path)


def _wait(coordinator, timeout=5):
    until = time.monotonic() + timeout
    while coordinator.get_status()["cycle_active"] and time.monotonic() < until:
        time.sleep(0.01)
    assert not coordinator.get_status()["cycle_active"]


def _coordinator(repo, probe, *, now=None, timers=None):
    timers = [] if timers is None else timers
    return MonitoringCoordinator(
        repo, ping_engine=probe,
        timer_factory=lambda seconds, callback: _Timer(seconds, callback, timers),
        now=now, initial_delay_seconds=999,
    )


def test_windows_ping_command_is_one_packet_and_classifies(mocked_process=None):
    calls = []
    class Process:
        returncode = 1
        def communicate(self, timeout=None): return ("Request timed out.", "")
    def popen(*args, **kwargs): calls.append((args, kwargs)); return Process()
    result = WindowsPingEngine(popen=popen).probe("10.0.0.1", 1500)
    assert result.status == "OFFLINE"
    assert calls[0][0][0] == ["ping.exe", "-n", "1", "-w", "1500", "10.0.0.1"]
    assert calls[0][1]["shell"] is False


def test_windows_ping_network_failure_and_cancel_terminates_process():
    network = WindowsPingEngine._classify("10.0.0.1", 1, "Destination host unreachable.", 10)
    assert network.status == "NETWORK_UNREACHABLE"
    cancelled = threading.Event()
    class Process:
        returncode = None
        terminated = False
        calls = 0
        def communicate(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                cancelled.set()
                raise subprocess.TimeoutExpired("ping.exe", timeout)
            return ("", "")
        def terminate(self): self.terminated = True
        def kill(self): self.terminated = True
    process = Process()
    result = WindowsPingEngine(popen=lambda *args, **kwargs: process).probe("10.0.0.1", 1500, cancelled)
    assert result.status == "CANCELLED"
    assert process.terminated


def test_concurrency_is_bounded_to_settings_maximum_for_200_devices(tmp_path):
    repo = _repo(tmp_path)
    for index in range(200): repo.create_device(f"Branch {index}", f"10.0.{index // 254}.{index % 254 + 1}")
    repo.update_settings(max_workers=5)
    probe = _Probe(delay=0.008)
    coordinator = _coordinator(repo, probe)
    coordinator.start()
    assert coordinator.check_all()
    _wait(coordinator, timeout=10)
    coordinator.stop()
    assert probe.calls == 200
    assert probe.maximum <= 5
    with repo.factory.connect(repo.database_path, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM check_result").fetchone()[0] == 200


@pytest.mark.parametrize("interval", (1, 2, 3))
def test_auto_interval_is_scheduled_after_cycle_completion(tmp_path, interval):
    repo = _repo(tmp_path); repo.create_device("A", "10.1.1.1")
    repo.update_settings(auto_check_interval_hours=interval)
    timers = []; coordinator = _coordinator(repo, _Probe(), timers=timers)
    coordinator.start(); assert coordinator.check_all(); _wait(coordinator)
    coordinator.stop()
    assert timers[-1].seconds == interval * 3600


def test_manual_selected_no_overlap_and_cancel(tmp_path):
    repo = _repo(tmp_path)
    device_ids = [repo.create_device("A", f"10.2.0.{index}") for index in range(1, 11)]
    probe = _Probe(delay=0.4); coordinator = _coordinator(repo, probe)
    coordinator.start()
    assert coordinator.check_selected(device_ids[:3])
    assert not coordinator.check_all()
    assert coordinator.cancel_current_cycle()
    _wait(coordinator)
    coordinator.stop()
    with repo.factory.connect(repo.database_path, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM check_result").fetchone()[0] == 3
        assert connection.execute("SELECT status FROM check_cycle").fetchone()[0] == "CANCELLED"


def test_offline_dates_alert_and_online_reset(tmp_path):
    repo = _repo(tmp_path); repo.create_device("A", "10.3.0.1")
    dates = iter((
        datetime(2026, 10, 1, tzinfo=None), datetime(2026, 10, 3, tzinfo=None),
        datetime(2026, 10, 9, tzinfo=None), datetime(2026, 10, 10, tzinfo=None),
    ))
    probe = _Probe(("OFFLINE", "OFFLINE", "OFFLINE", "ONLINE"))
    coordinator = _coordinator(repo, probe, now=lambda: next(dates))
    coordinator.start()
    for _ in range(4):
        assert coordinator.check_all(); _wait(coordinator)
    coordinator.stop()
    with repo.factory.connect(repo.database_path, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM offline_incident WHERE resolved_at IS NOT NULL").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM device_daily_failure").fetchone()[0] == 0


def test_network_error_states_do_not_count_offline(tmp_path):
    repo = _repo(tmp_path); repo.create_device("A", "10.4.0.1")
    probe = _Probe(("NETWORK_UNREACHABLE", "ERROR", "UNKNOWN"))
    coordinator = _coordinator(repo, probe)
    coordinator.start()
    for _ in range(3): assert coordinator.check_all(); _wait(coordinator)
    coordinator.stop()
    with repo.factory.connect(repo.database_path, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM device_daily_failure").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM offline_incident").fetchone()[0] == 0


def test_restart_persists_history_and_lock_failure_is_safe(tmp_path):
    repo = _repo(tmp_path); repo.create_device("A", "10.5.0.1")
    first = _coordinator(repo, _Probe()); first.start(); assert first.check_all(); _wait(first); first.stop()
    second = _coordinator(FingerMonitoringRepository(repo.database_path), _Probe()); second.start(); assert second.check_all(); _wait(second); second.stop()
    locker = sqlite3.connect(repo.database_path, timeout=0)
    try:
        locker.execute("BEGIN EXCLUSIVE")
        locked = _coordinator(repo, _Probe())
        assert not locked.start()
        assert any(event.name == "START_FAILED" for event in locked.drain_events())
    finally:
        locker.rollback(); locker.close()
    with repo.factory.connect(repo.database_path, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM check_cycle").fetchone()[0] == 2


def test_stop_returns_without_leaving_active_cycle(tmp_path):
    repo = _repo(tmp_path)
    for number in range(1, 8): repo.create_device("A", f"10.6.0.{number}")
    coordinator = _coordinator(repo, _Probe(delay=1))
    coordinator.start(); assert coordinator.check_all()
    coordinator.stop(); _wait(coordinator)
    assert coordinator.get_status()["running"] is False
