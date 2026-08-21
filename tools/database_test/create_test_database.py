"""Create an explicitly located, non-production OAS-K test database."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.database import (  # noqa: E402
    BackupManager,
    DatabaseValidator,
    SchemaManager,
)

PRODUCTION_DATA_ROOT = Path("D:/OAS-K/Data")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create and validate an isolated OAS-K schema-v1 test database."
        )
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Explicit .db output path outside the production data root.",
    )
    parser.add_argument(
        "--application-version",
        default="DB1-manual-test",
        help="Metadata application version for the test database.",
    )
    parser.add_argument(
        "--create-parent",
        action="store_true",
        help="Create the output parent directory when it does not exist.",
    )
    parser.add_argument(
        "--backup",
        type=Path,
        help="Optional explicit path for a validated SQLite test backup.",
    )
    return parser.parse_args()


def validate_test_path(path: Path) -> Path:
    """Reject production-root and non-database destinations."""

    resolved = path.expanduser().resolve()
    production_root = PRODUCTION_DATA_ROOT.resolve()
    if resolved == production_root or production_root in resolved.parents:
        raise ValueError(
            "The manual DB1 test tool refuses the production data root."
        )
    if resolved.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
        raise ValueError(
            "Test database output must use .db, .sqlite, or .sqlite3."
        )
    return resolved


def count_tables(path: Path) -> int:
    """Return the number of non-internal SQLite tables."""

    connection = sqlite3.connect(
        f"{path.as_uri()}?mode=ro",
        uri=True,
    )
    try:
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchone()
        return int(row[0]) if row is not None else 0
    finally:
        connection.close()


def main() -> None:
    arguments = parse_arguments()
    output = validate_test_path(arguments.output)
    if output.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing test database: {output}"
        )

    metadata = SchemaManager().initialize_database(
        output,
        arguments.application_version,
        create_parent=arguments.create_parent,
    )
    validation = DatabaseValidator().validate_or_raise(output)

    print(f"Database: {output}")
    print(f"Schema version: {metadata.schema_version}")
    print(f"Table count: {count_tables(output)}")
    print(f"Validation: {'PASS' if validation.is_valid else 'FAIL'}")

    if arguments.backup is not None:
        backup = validate_test_path(arguments.backup)
        result = BackupManager().create_backup(
            output,
            backup,
            create_parent=arguments.create_parent,
        )
        print(f"Backup: {result.destination_path}")
        print(f"Backup SHA-256: {result.sha256}")


if __name__ == "__main__":
    main()
