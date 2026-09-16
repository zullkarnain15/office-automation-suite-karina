"""Temporary database fixtures for DB1 tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.database import SchemaManager


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    """Return a fresh schema-v1 database inside pytest's temp directory."""

    path = tmp_path / "OAS-K-test.db"
    SchemaManager().initialize_database(
        path,
        application_version="test-1.0.0",
    )
    return path
