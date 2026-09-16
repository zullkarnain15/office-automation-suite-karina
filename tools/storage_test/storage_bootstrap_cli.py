"""Explicit manual DB3 storage validation/bootstrap CLI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.storage import (  # noqa: E402
    StorageBootstrapRequest,
    StorageBootstrapService,
    resolve_storage_layout,
    validate_data_root,
    validate_profile_reference,
)
from shared.storage.registry import (  # noqa: E402
    StorageRegistryService,
    WindowsRegistryBackend,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely inspect or explicitly initialize an OAS-K Data Root."
    )
    parser.add_argument(
        "--data-root",
        required=True,
        type=Path,
        help="Explicit test or production Data Root.",
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--validate-only", action="store_true")
    action.add_argument("--initialize", action="store_true")
    action.add_argument("--show-layout", action="store_true")
    action.add_argument(
        "--validate-profile",
        type=Path,
        metavar="RELATIVE_JSON_PATH",
    )
    parser.add_argument("--application-version", default="manual-db3")
    parser.add_argument("--write-registry", action="store_true")
    parser.add_argument("--confirm-registry-write", action="store_true")
    arguments = parser.parse_args()

    if arguments.write_registry and not arguments.confirm_registry_write:
        parser.error(
            "--write-registry requires --confirm-registry-write."
        )
    if arguments.write_registry and not arguments.initialize:
        parser.error("--write-registry is only valid with --initialize.")

    if arguments.validate_only:
        payload = validate_data_root(arguments.data_root)
    elif arguments.show_layout:
        payload = resolve_storage_layout(arguments.data_root)
    elif arguments.validate_profile is not None:
        payload = validate_profile_reference(
            arguments.data_root,
            arguments.validate_profile,
        )
    else:
        registry = None
        if arguments.write_registry:
            registry = StorageRegistryService(WindowsRegistryBackend())
        payload = StorageBootstrapService(registry).initialize_storage(
            StorageBootstrapRequest(
                data_root=arguments.data_root,
                application_version=arguments.application_version,
                update_registry=arguments.write_registry,
            )
        )

    print(json.dumps(_json_value(payload), ensure_ascii=False, indent=2))
    return 0 if not getattr(payload, "errors", ()) else 1


def _json_value(value: object) -> object:
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {
            str(key): _json_value(item) for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (Path, Enum)):
        return str(value)
    return value


if __name__ == "__main__":
    raise SystemExit(main())
