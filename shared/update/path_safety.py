"""Path safety helpers for application update workflows."""

from __future__ import annotations

from pathlib import Path

from shared.update.exceptions import UpdateTransactionError


def resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def is_relative_to(path: str | Path, parent: str | Path) -> bool:
    path_value = resolved(path)
    parent_value = resolved(parent)
    return path_value == parent_value or parent_value in path_value.parents


def require_under(path: str | Path, parent: str | Path, message: str) -> Path:
    value = resolved(path)
    root = resolved(parent)
    if value != root and root not in value.parents:
        raise UpdateTransactionError(message)
    return value


def reject_overlap(left: str | Path, right: str | Path, message: str) -> None:
    left_value = resolved(left)
    right_value = resolved(right)
    if (
        left_value == right_value
        or left_value in right_value.parents
        or right_value in left_value.parents
    ):
        raise UpdateTransactionError(message)


def require_distinct_application_and_data_roots(
    application_root: str | Path,
    data_root: str | Path,
) -> None:
    app = resolved(application_root)
    data = resolved(data_root)
    if app == data:
        raise UpdateTransactionError("Application Root tidak boleh sama dengan Data Root.")
