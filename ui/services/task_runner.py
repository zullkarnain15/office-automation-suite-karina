"""Small centralized worker pool that marshals callbacks through Tk.after."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from queue import Empty, SimpleQueue
from typing import Any


@dataclass(frozen=True, slots=True)
class TaskProgress:
    message: str
    percent: int | None = None


@dataclass(frozen=True, slots=True)
class TaskResult:
    task_id: str
    success: bool
    value: Any = None
    error: str | None = None
    cancelled: bool = False


@dataclass(slots=True)
class TaskHandle:
    task_id: str
    future: Future[Any]
    cancel_event: threading.Event = field(default_factory=threading.Event)
    cancellable: bool = True

    def cancel(self) -> bool:
        if not self.cancellable:
            return False
        self.cancel_event.set()
        return self.future.cancel()


class TaskRunner:
    def __init__(self, after: Callable[[int, Callable[[], None]], Any]) -> None:
        self.after = after
        self.executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="oas-k-ui",
        )
        self._accepting = True
        self._handles: dict[str, TaskHandle] = {}
        self._messages: SimpleQueue[tuple[str, str, Any, Callable]] = SimpleQueue()
        self._drain_scheduled = False
        self._drain_after_id: Any = None

    def submit(
        self,
        function: Callable[[], Any],
        *,
        on_done: Callable[[TaskResult], None],
        on_progress: Callable[[TaskProgress], None] | None = None,
        cancellable: bool = True,
    ) -> TaskHandle:
        if not self._accepting:
            raise RuntimeError("Task runner tidak menerima task baru.")
        task_id = uuid.uuid4().hex
        if on_progress is not None:
            self.after(0, lambda: on_progress(TaskProgress("Memulai task", 0)))
        future = self.executor.submit(function)
        handle = TaskHandle(task_id, future, cancellable=cancellable)
        self._handles[task_id] = handle
        self._ensure_drain()

        def completed(done: Future[Any]) -> None:
            try:
                value = done.result()
                result = TaskResult(task_id, True, value=value)
            except Exception as exc:
                result = TaskResult(task_id, False, error=str(exc))

            # A worker may only publish plain data. Tk.after and the UI
            # callback are both invoked by the Tk-thread queue drain.
            if self._accepting:
                self._messages.put(("done", task_id, result, on_done))

        future.add_done_callback(completed)
        return handle

    def submit_reporting(
        self,
        function: Callable[[Callable[[Any], None]], Any],
        *,
        on_done: Callable[[TaskResult], None],
        on_progress: Callable[[Any], None],
        cancellable: bool = True,
    ) -> TaskHandle:
        """Run a worker with a queue-backed, Tk-safe progress reporter."""

        if not self._accepting:
            raise RuntimeError("Task runner tidak menerima task baru.")
        task_id = uuid.uuid4().hex

        def report(value: Any) -> None:
            self._messages.put(("progress", task_id, value, on_progress))

        future = self.executor.submit(function, report)
        handle = TaskHandle(task_id, future, cancellable=cancellable)
        self._handles[task_id] = handle
        self._ensure_drain()

        def completed(done: Future[Any]) -> None:
            try:
                value = done.result()
                result = TaskResult(task_id, True, value=value)
            except Exception as exc:
                result = TaskResult(task_id, False, error=str(exc))
            if self._accepting:
                self._messages.put(("done", task_id, result, on_done))

        future.add_done_callback(completed)
        return handle

    def _ensure_drain(self) -> None:
        if self._drain_scheduled:
            return
        self._drain_scheduled = True
        self._drain_after_id = self.after(0, self._drain_completed)

    def _drain_completed(self) -> None:
        self._drain_scheduled = False
        self._drain_after_id = None
        while True:
            try:
                kind, task_id, value, callback = self._messages.get_nowait()
            except Empty:
                break
            if kind == "done":
                self._handles.pop(task_id, None)
            callback(value)
        if self._accepting and self._handles:
            self._drain_scheduled = True
            self._drain_after_id = self.after(25, self._drain_completed)

    def shutdown(self) -> None:
        self._accepting = False
        if self._drain_after_id is not None:
            owner = getattr(self.after, "__self__", None)
            cancel = getattr(owner, "after_cancel", None)
            if cancel is not None:
                try:
                    cancel(self._drain_after_id)
                except Exception:
                    pass
            self._drain_after_id = None
            self._drain_scheduled = False
        for handle in tuple(self._handles.values()):
            handle.cancel_event.set()
        self._handles.clear()
        while True:
            try:
                self._messages.get_nowait()
            except Empty:
                break
        self.executor.shutdown(wait=False, cancel_futures=True)

    @property
    def accepting(self) -> bool:
        return self._accepting
