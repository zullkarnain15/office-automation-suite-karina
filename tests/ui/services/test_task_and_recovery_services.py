"""Task runner and recovery confirmation contracts."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from shared.storage.registry import FakeRegistryBackend, StorageRegistryService
from ui.services.recovery_ui_service import RecoveryUIService
from ui.services.task_runner import TaskRunner


def test_task_runner_delivers_via_after_contract() -> None:
    callbacks = []
    after_threads = []

    def after(delay, callback):
        after_threads.append(threading.current_thread().name)
        callbacks.append(callback)

    results = []
    runner = TaskRunner(after)
    handle = runner.submit(lambda: 42, on_done=results.append)
    handle.future.result(timeout=5)
    for callback in list(callbacks):
        callback()
    runner.shutdown()
    assert results[0].success and results[0].value == 42
    assert after_threads
    assert after_threads == [threading.main_thread().name]


def test_worker_never_calls_after_or_ui_callback() -> None:
    callbacks = []
    after_threads = []
    callback_threads = []

    def after(delay, callback):
        after_threads.append(threading.current_thread().name)
        callbacks.append(callback)

    runner = TaskRunner(after)
    handle = runner.submit(
        lambda: threading.current_thread().name,
        on_done=lambda result: callback_threads.append(threading.current_thread().name),
    )
    worker_name = handle.future.result(timeout=5)
    for callback in list(callbacks):
        callback()
    runner.shutdown()

    assert worker_name.startswith("oas-k-ui")
    assert after_threads == [threading.main_thread().name]
    assert callback_threads == [threading.main_thread().name]


def test_reporting_worker_streams_only_through_tk_drain() -> None:
    callbacks = []
    progress = []
    done = []
    runner = TaskRunner(lambda delay, callback: callbacks.append(callback))

    def work(report):
        report(("stage", threading.current_thread().name))
        return "complete"

    handle = runner.submit_reporting(
        work,
        on_done=done.append,
        on_progress=lambda value: progress.append(
            (value, threading.current_thread().name)
        ),
    )
    handle.future.result(timeout=5)
    for callback in list(callbacks):
        callback()
    runner.shutdown()
    assert progress[0][0][1].startswith("oas-k-ui")
    assert progress[0][1] == threading.main_thread().name
    assert done[0].success and done[0].value == "complete"


def test_task_runner_handles_exception() -> None:
    callbacks = []
    results = []
    runner = TaskRunner(lambda delay, callback: callbacks.append(callback))

    def fail():
        raise RuntimeError("worker failed")

    handle = runner.submit(fail, on_done=results.append)
    with pytest.raises(RuntimeError):
        handle.future.result(timeout=5)
    for callback in callbacks:
        callback()
    runner.shutdown()
    assert not results[0].success
    assert "worker failed" in results[0].error


def test_task_runner_rejects_after_shutdown() -> None:
    runner = TaskRunner(lambda delay, callback: None)
    runner.shutdown()
    with pytest.raises(RuntimeError):
        runner.submit(lambda: None, on_done=lambda result: None)


def test_task_runner_shutdown_cancels_pending_tk_drain() -> None:
    class Scheduler:
        def __init__(self) -> None:
            self.cancelled = []

        def after(self, delay, callback):
            return "after-drain"

        def after_cancel(self, callback_id):
            self.cancelled.append(callback_id)

    scheduler = Scheduler()
    runner = TaskRunner(scheduler.after)
    handle = runner.submit(lambda: "done", on_done=lambda result: None)
    handle.future.result(timeout=5)

    runner.shutdown()

    assert scheduler.cancelled == ["after-drain"]


def test_reset_requires_typed_reset(tmp_path: Path) -> None:
    service = RecoveryUIService(
        StorageRegistryService(FakeRegistryBackend()),
        application_version="ui2",
    )
    with pytest.raises(ValueError, match="RESET"):
        service.reset(
            tmp_path,
            typed_value="reset",
            confirmed=True,
            write_registry=False,
        )


def test_recovery_service_construction_has_no_action(
    tmp_path: Path,
) -> None:
    service = RecoveryUIService(
        StorageRegistryService(FakeRegistryBackend()),
        application_version="ui2",
    )
    assert not (tmp_path / "database").exists()
    assert service.application_version == "ui2"
