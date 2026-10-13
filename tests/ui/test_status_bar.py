"""Application footer database-status behavior."""

from __future__ import annotations

from types import SimpleNamespace

from ui.models import StatusMetadata
from ui.widgets.status_bar import StatusBar


def test_message_updates_do_not_reset_database_status(tk_root) -> None:
    status_bar = StatusBar(tk_root, "test")
    status_bar.set_storage_status("Database: Valid (Schema v3)")

    status_bar.update_metadata(StatusMetadata("Ready", "Dashboard"))

    assert status_bar.storage_label.cget("text") == "Database: Valid (Schema v3)"


def test_explicit_database_status_still_updates_footer(tk_root) -> None:
    status_bar = StatusBar(tk_root, "test")

    status_bar.update_metadata(
        StatusMetadata(
            "Ready",
            "Dashboard",
            storage_status="Database: Tidak valid",
        )
    )

    assert status_bar.storage_label.cget("text") == "Database: Tidak valid"


def test_storage_status_text_covers_database_states() -> None:
    from ui.app import OASKUnifiedApp

    assert OASKUnifiedApp._storage_status_text(
        SimpleNamespace(database_valid=True, schema_version=3)
    ) == "Database: Valid (Schema v3)"
    assert OASKUnifiedApp._storage_status_text(
        SimpleNamespace(database_valid=False, database_exists=True)
    ) == "Database: Tidak valid"
    assert OASKUnifiedApp._storage_status_text(
        SimpleNamespace(
            database_valid=False,
            database_exists=False,
            database_path=None,
        )
    ) == "Database: Tidak tersedia"
