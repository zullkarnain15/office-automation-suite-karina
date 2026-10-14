"""Presentation-only conversion of existing UI task results to mascot outcomes."""

from __future__ import annotations

from typing import Any


def classify_mascot_outcome(
    task_result: Any,
    *,
    warning_statuses: tuple[str, ...] = (),
) -> str | None:
    """Use already-established UI result semantics without inspecting engines."""
    if not task_result.success:
        return "error"
    value = task_result.value
    if getattr(value, "cancelled", False):
        return None
    if not getattr(value, "success", False):
        return "error"
    if getattr(value, "status", "") in warning_statuses:
        return "warning"
    if getattr(value, "warning_count", 0):
        return "warning"
    return "success"
