from __future__ import annotations

from ui.services.module_job_coordinator import ModuleJobCoordinator


def test_accepts_two_compatible_jobs_and_rejects_third(tmp_path) -> None:
    coordinator = ModuleJobCoordinator(max_active=2)
    first = coordinator.try_start(
        "ATTENDANCE", "Attendance", write_paths=(tmp_path / "Attendance",)
    )
    second = coordinator.try_start(
        "HRIS", "HRIS", write_paths=(tmp_path / "HRIS",)
    )
    third = coordinator.try_start(
        "UTILITIES", "Utilities", write_paths=(tmp_path / "Utilities",)
    )

    assert first.accepted and second.accepted
    assert not third.accepted and "Batas 2" in third.message


def test_rejects_same_module_resource_and_path_conflicts(tmp_path) -> None:
    coordinator = ModuleJobCoordinator()
    first = coordinator.try_start(
        "OUTLOOK_REVISI",
        "Outlook Revisi",
        resources=("OUTLOOK_CLASSIC",),
        write_paths=(tmp_path / "Output" / "Outlook-Revisi",),
    )

    same_module = coordinator.try_start("OUTLOOK_REVISI", "Outlook Revisi")
    same_resource = coordinator.try_start(
        "MAIL_TOOL", "Mail Tool", resources=("OUTLOOK_CLASSIC",)
    )
    same_path = coordinator.try_start(
        "UTILITIES",
        "Utilities",
        read_paths=(tmp_path / "Output" / "Outlook-Revisi" / "Report",),
    )

    assert first.accepted
    assert not same_module.accepted and "sudah berjalan" in same_module.message
    assert not same_resource.accepted and "OUTLOOK_CLASSIC" in same_resource.message
    assert not same_path.accepted and "berbenturan" in same_path.message


def test_shared_read_path_is_safe_and_finish_frees_slot(tmp_path) -> None:
    coordinator = ModuleJobCoordinator()
    snapshots = []
    unsubscribe = coordinator.subscribe(lambda jobs: snapshots.append(len(jobs)))
    shared = tmp_path / "source"
    first = coordinator.try_start("A", "A", read_paths=(shared,))
    second = coordinator.try_start("B", "B", read_paths=(shared,))

    assert first.accepted and second.accepted
    assert coordinator.finish(first.job.job_id)
    third = coordinator.try_start("C", "C", write_paths=(tmp_path / "other",))
    assert third.accepted
    assert snapshots == [0, 1, 2, 1, 2]
    unsubscribe()
