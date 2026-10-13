"""Application-lifetime monitoring coordinator, independent of Tkinter."""

from __future__ import annotations

import queue
import threading
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from shared.finger_monitoring.ping_engine import PingProbeResult, WindowsPingEngine

# Jakarta is permanently UTC+07:00 (no daylight saving time).  A fixed offset
# avoids requiring the optional IANA ``tzdata`` package in a Windows EXE.
JAKARTA = timezone(timedelta(hours=7), name="Asia/Jakarta")


@dataclass(frozen=True, slots=True)
class MonitoringEvent:
    name: str
    payload: dict[str, Any]


class MonitoringCoordinator:
    """Coordinate one bounded ping cycle at a time while OAS-K is open."""

    def __init__(
        self,
        repository,
        *,
        ping_engine: WindowsPingEngine | None = None,
        timer_factory: Callable[[float, Callable[[], None]], Any] | None = None,
        now: Callable[[], datetime] | None = None,
        initial_delay_seconds: float = 0.05,
        activity_gate=None,
        cycle_completed_callback=None,
    ) -> None:
        self.repository = repository
        self.ping_engine = ping_engine or WindowsPingEngine()
        self.timer_factory = timer_factory or self._default_timer
        self.now = now or (lambda: datetime.now(JAKARTA))
        self.initial_delay_seconds = initial_delay_seconds
        self.activity_gate = activity_gate
        self.cycle_completed_callback = cycle_completed_callback
        self.events: queue.SimpleQueue[MonitoringEvent] = queue.SimpleQueue()
        self._lock = threading.RLock()
        self._running = False
        self._cycle_active = False
        self._cancel_event: threading.Event | None = None
        self._timer = None
        self._manager: ThreadPoolExecutor | None = None
        self._workers: ThreadPoolExecutor | None = None
        self._active_futures: set[Future] = set()
        self._active_cycle_id: int | None = None
        self._last_error: str | None = None
        self._next_delay_seconds: float | None = None

    @staticmethod
    def _default_timer(seconds: float, callback: Callable[[], None]):
        timer = threading.Timer(seconds, callback)
        timer.daemon = True
        return timer

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return False
            try:
                self.repository.initialize()
                settings = self.repository.get_settings()
            except Exception as exc:
                self._last_error = str(exc)
                self._emit("START_FAILED", error=self._last_error)
                return False
            self._workers = ThreadPoolExecutor(max_workers=int(settings["max_workers"]), thread_name_prefix="oas-k-finger-ping")
            self._manager = ThreadPoolExecutor(max_workers=1, thread_name_prefix="oas-k-finger-cycle")
            self._running = True
            self._schedule(self.initial_delay_seconds)
        self._emit("STARTED", max_workers=int(settings["max_workers"]))
        return True

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._cancel_timer()
            self._cancel_current_locked()
            manager, workers = self._manager, self._workers
            self._manager = None
            self._workers = None
        # wait=False avoids blocking app close; ping workers receive cancellation
        # and their subprocesses are terminated by the engine's short polling loop.
        if manager is not None:
            manager.shutdown(wait=False, cancel_futures=True)
        if workers is not None:
            workers.shutdown(wait=False, cancel_futures=True)
        self._emit("STOPPED")

    def check_all(self) -> bool:
        return self._begin_cycle("CHECK_ALL", None)

    def check_selected(self, device_ids) -> bool:
        return self._begin_cycle("CHECK_SELECTED", tuple(device_ids))

    def cancel_current_cycle(self) -> bool:
        with self._lock:
            if not self._cycle_active:
                return False
            self._cancel_current_locked()
        self._emit("CANCEL_REQUESTED", cycle_id=self._active_cycle_id)
        return True

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "cycle_active": self._cycle_active,
                "cycle_id": self._active_cycle_id,
                "queued_or_running_pings": sum(not item.done() for item in self._active_futures),
                "last_error": self._last_error,
                "next_delay_seconds": self._next_delay_seconds,
            }

    def drain_events(self) -> tuple[MonitoringEvent, ...]:
        events = []
        while True:
            try:
                events.append(self.events.get_nowait())
            except queue.Empty:
                return tuple(events)

    def _emit(self, name: str, **payload: Any) -> None:
        """Publish plain data only; a future Tk page may drain this queue."""
        self.events.put(MonitoringEvent(name, payload))

    def _begin_cycle(self, source: str, selected_ids) -> bool:
        with self._lock:
            if not self._running or self._cycle_active or self._manager is None:
                return False
            devices = self.repository.list_devices() if selected_ids is None else self.repository.list_active_devices_by_ids(selected_ids)
            self._cycle_active = True
            self._cancel_event = threading.Event()
            self._manager.submit(self._run_cycle, source, devices, self._cancel_event)
            return True

    def _run_scheduled_cycle(self) -> None:
        with self._lock:
            self._timer = None
            running = self._running
        if running:
            self._begin_cycle("AUTO", None)

    def _run_cycle(self, source: str, devices, cancel_event: threading.Event) -> None:
        if self.activity_gate is not None:
            try:
                with self.activity_gate.activity("MONITORING"):
                    self._run_cycle_inner(source, devices, cancel_event)
            except Exception as exc:
                with self._lock:
                    self._cycle_active = False
                    self._cancel_event = None
                    running = self._running
                self._emit("CYCLE_ERROR", cycle_id=None, error=str(exc))
                if running:
                    self._schedule_from_settings()
            return
        self._run_cycle_inner(source, devices, cancel_event)

    def _run_cycle_inner(self, source: str, devices, cancel_event: threading.Event) -> None:
        cycle_id = None
        cycle_status = "COMPLETED"
        try:
            cycle_id = self.repository.create_cycle(source, len(devices))
            with self._lock:
                self._active_cycle_id = cycle_id
            self._emit("CYCLE_STARTED", cycle_id=cycle_id, source=source, requested_devices=len(devices))
            settings = self.repository.get_settings()
            workers = self._workers
            if workers is None:
                raise RuntimeError("Monitoring workers sudah dihentikan.")
            futures = {
                workers.submit(self.ping_engine.probe, row["ip_address"], int(settings["ping_timeout_ms"]), cancel_event): row
                for row in devices
            }
            with self._lock:
                self._active_futures = set(futures)
            for future in as_completed(futures):
                device = futures[future]
                try:
                    result = future.result()
                except CancelledError:
                    result = PingProbeResult("CANCELLED", device["ip_address"], diagnostic="CANCELLED_BEFORE_WORKER_START")
                except Exception as exc:
                    result = PingProbeResult("ERROR", device["ip_address"], diagnostic=f"PING_WORKER_FAILED: {exc}")
                observed_date = self.now().astimezone(JAKARTA).date().isoformat()
                persisted = self.repository.persist_check_outcome(
                    cycle_id, device["device_id"], result.status,
                    latency_ms=result.latency_ms, exit_code=result.exit_code,
                    diagnostic=result.diagnostic, observed_date=observed_date,
                    alert_threshold=int(settings["offline_alert_observed_dates"]),
                )
                self._emit("DEVICE_RESULT", cycle_id=cycle_id, device_id=device["device_id"], result=asdict(result), **persisted)
            if cancel_event.is_set():
                cycle_status = "CANCELLED"
        except Exception as exc:
            cycle_status = "FAILED"
            self._emit("CYCLE_ERROR", cycle_id=cycle_id, error=str(exc))
        finally:
            if cycle_id is not None:
                try:
                    self.repository.complete_cycle(cycle_id, cycle_status)
                except Exception as exc:
                    self._emit("CYCLE_FINALIZE_ERROR", cycle_id=cycle_id, error=str(exc))
            with self._lock:
                self._active_futures.clear()
                self._active_cycle_id = None
                self._cycle_active = False
                running = self._running
                self._cancel_event = None
            self._emit("CYCLE_FINISHED", cycle_id=cycle_id, status=cycle_status)
            if (
                cycle_id is not None
                and self.cycle_completed_callback is not None
            ):
                try:
                    self.cycle_completed_callback(cycle_id, source, cycle_status)
                except Exception as exc:
                    self._emit("CYCLE_CALLBACK_ERROR", cycle_id=cycle_id, error=str(exc))
            if running:
                self._schedule_from_settings()

    def _schedule_from_settings(self) -> None:
        try:
            interval = int(self.repository.get_settings()["auto_check_interval_hours"])
        except Exception as exc:
            self._emit("SCHEDULE_ERROR", error=str(exc))
            return
        self._schedule(interval * 3600)

    def _schedule(self, seconds: float) -> None:
        with self._lock:
            if not self._running:
                return
            self._cancel_timer()
            timer = self.timer_factory(seconds, self._run_scheduled_cycle)
            self._timer = timer
            self._next_delay_seconds = seconds
            timer.start()

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            try:
                self._timer.cancel()
            finally:
                self._timer = None
                self._next_delay_seconds = None

    def _cancel_current_locked(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
        for future in tuple(self._active_futures):
            future.cancel()
