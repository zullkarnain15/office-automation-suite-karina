"""Application-wide admission control for long-running module jobs."""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


MAX_ACTIVE_MODULE_JOBS = 2


@dataclass(frozen=True, slots=True)
class ActiveModuleJob:
    job_id: str
    module: str
    title: str
    resources: frozenset[str]
    read_paths: tuple[Path, ...]
    write_paths: tuple[Path, ...]
    exclusive: bool = False


@dataclass(frozen=True, slots=True)
class JobStartResult:
    accepted: bool
    job: ActiveModuleJob | None = None
    message: str = ""


class ModuleJobCoordinator:
    """Allow at most two compatible foreground module jobs at once."""

    def __init__(self, max_active: int = MAX_ACTIVE_MODULE_JOBS) -> None:
        if max_active < 1:
            raise ValueError("max_active harus minimal 1.")
        self.max_active = max_active
        self._jobs: dict[str, ActiveModuleJob] = {}
        self._listeners: list[Callable[[tuple[ActiveModuleJob, ...]], None]] = []
        self._lock = threading.RLock()

    def try_start(
        self,
        module: str,
        title: str,
        *,
        resources: Iterable[str] = (),
        read_paths: Iterable[str | Path | None] = (),
        write_paths: Iterable[str | Path | None] = (),
        exclusive: bool = False,
    ) -> JobStartResult:
        normalized_module = module.strip().upper()
        normalized_resources = frozenset(
            resource.strip().upper() for resource in resources if resource.strip()
        )
        normalized_reads = self._normalize_paths(read_paths)
        normalized_writes = self._normalize_paths(write_paths)

        with self._lock:
            active = tuple(self._jobs.values())
            if any(job.module == normalized_module for job in active):
                return self._rejected(
                    f"{title} sudah berjalan. Satu modul tidak boleh menjalankan dua job sekaligus."
                )
            if len(active) >= self.max_active:
                names = " + ".join(job.title for job in active)
                return self._rejected(
                    f"Batas {self.max_active} job aktif sudah tercapai ({names}). "
                    "Tunggu salah satu job selesai."
                )
            if exclusive and active:
                return self._rejected(
                    f"{title} memerlukan akses eksklusif. Tunggu job aktif selesai."
                )
            for job in active:
                if job.exclusive:
                    return self._rejected(
                        f"{job.title} sedang memakai akses eksklusif. Tunggu job tersebut selesai."
                    )
                shared = normalized_resources.intersection(job.resources)
                if shared:
                    return self._rejected(
                        f"{title} berbenturan dengan {job.title} pada resource "
                        f"{', '.join(sorted(shared))}."
                    )
                if self._paths_conflict(
                    normalized_reads,
                    normalized_writes,
                    job.read_paths,
                    job.write_paths,
                ):
                    return self._rejected(
                        f"{title} memakai sumber/output yang berbenturan dengan "
                        f"{job.title}. Pilih folder berbeda atau tunggu job selesai."
                    )

            job = ActiveModuleJob(
                job_id=uuid.uuid4().hex,
                module=normalized_module,
                title=title,
                resources=normalized_resources,
                read_paths=normalized_reads,
                write_paths=normalized_writes,
                exclusive=exclusive,
            )
            self._jobs[job.job_id] = job
            snapshot = tuple(self._jobs.values())
        self._notify(snapshot)
        return JobStartResult(True, job)

    def finish(self, job_id: str | None) -> bool:
        if not job_id:
            return False
        with self._lock:
            removed = self._jobs.pop(job_id, None)
            snapshot = tuple(self._jobs.values())
        if removed is not None:
            self._notify(snapshot)
            return True
        return False

    def snapshot(self) -> tuple[ActiveModuleJob, ...]:
        with self._lock:
            return tuple(self._jobs.values())

    @property
    def has_active_jobs(self) -> bool:
        with self._lock:
            return bool(self._jobs)

    def subscribe(
        self, listener: Callable[[tuple[ActiveModuleJob, ...]], None]
    ) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)
            snapshot = tuple(self._jobs.values())
        listener(snapshot)

        def unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return unsubscribe

    @staticmethod
    def _rejected(message: str) -> JobStartResult:
        return JobStartResult(False, message=message)

    @staticmethod
    def _normalize_paths(
        paths: Iterable[str | Path | None],
    ) -> tuple[Path, ...]:
        normalized: list[Path] = []
        seen: set[str] = set()
        for value in paths:
            if value is None or not str(value).strip():
                continue
            path = Path(value).expanduser().resolve(strict=False)
            key = os.path.normcase(str(path))
            if key not in seen:
                seen.add(key)
                normalized.append(path)
        return tuple(normalized)

    @classmethod
    def _paths_conflict(
        cls,
        reads_a: tuple[Path, ...],
        writes_a: tuple[Path, ...],
        reads_b: tuple[Path, ...],
        writes_b: tuple[Path, ...],
    ) -> bool:
        pairs = [
            *((write, other) for write in writes_a for other in reads_b),
            *((write, other) for write in writes_a for other in writes_b),
            *((read, other) for read in reads_a for other in writes_b),
        ]
        return any(cls._overlaps(left, right) for left, right in pairs)

    @staticmethod
    def _overlaps(left: Path, right: Path) -> bool:
        if os.path.normcase(str(left)) == os.path.normcase(str(right)):
            return True
        try:
            return left in right.parents or right in left.parents
        except (OSError, ValueError):
            return False

    def _notify(self, snapshot: tuple[ActiveModuleJob, ...]) -> None:
        with self._lock:
            listeners = tuple(self._listeners)
        for listener in listeners:
            listener(snapshot)
