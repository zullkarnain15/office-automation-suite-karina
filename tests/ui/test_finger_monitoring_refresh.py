"""Refresh requests should keep only the latest pending view of monitoring data."""

from types import SimpleNamespace

from ui.pages.finger_monitoring_page import FingerMonitoringPage
from ui.services.task_runner import TaskResult


def test_refresh_coalesces_repeated_requests_without_stale_render():
    queued = []
    rendered = []
    errors = []

    def submit(work, *, on_done):
        queued.append((work, on_done))

    page = FingerMonitoringPage.__new__(FingerMonitoringPage)
    page._refresh_inflight = set()
    page._refresh_latest = {}
    page.services = SimpleNamespace(
        task_runner=SimpleNamespace(submit=submit),
        dialog_service=SimpleNamespace(error=lambda *args: errors.append(args)),
    )
    for value in (1, 2, 3):
        page._background(lambda value=value: value, rendered.append, refresh_key="status")

    assert len(queued) == 1
    work, done = queued.pop()
    done(TaskResult("first", True, value=work()))
    assert rendered == []
    assert len(queued) == 1
    work, done = queued.pop()
    done(TaskResult("latest", True, value=work()))
    assert rendered == [3]
    assert errors == []
