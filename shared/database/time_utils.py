"""Small ISO date/time helpers for the persistence boundary."""

from __future__ import annotations

from datetime import date, datetime


def current_timestamp() -> str:
    """Return a local ISO 8601 timestamp with second precision."""

    return datetime.now().replace(microsecond=0).isoformat()


def validate_date_pair(
    period_start: str | None,
    period_end: str | None,
) -> None:
    """Validate a nullable, complete, ordered ISO date pair."""

    if period_start is None and period_end is None:
        return
    if period_start is None or period_end is None:
        raise ValueError(
            "period_start and period_end must both be provided or both be null."
        )

    try:
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
    except ValueError as exc:
        raise ValueError("Periods must use ISO date format YYYY-MM-DD.") from exc

    if start > end:
        raise ValueError("period_start must not be after period_end.")
