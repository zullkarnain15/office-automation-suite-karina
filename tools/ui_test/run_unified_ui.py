"""Explicit manual launcher for the Unified UI Settings shell."""

from __future__ import annotations

import argparse
import logging
import sys
import tkinter as tk
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.app_config import APP_VERSION  # noqa: E402
from shared.storage.registry import (  # noqa: E402
    FakeRegistryBackend,
    StorageRegistryService,
)
from ui.app import OASKUnifiedApp  # noqa: E402
from ui.context import AppContext  # noqa: E402
from ui.services.service_container import (  # noqa: E402
    build_default_app_services,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the source-only OAS-K Unified UI."
    )
    parser.add_argument(
        "--test-data-root",
        type=Path,
        help=(
            "Use this explicit test suggestion with an in-memory fake Registry. "
            "The folder is not created until Initialize is confirmed."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    root = tk.Tk()
    context = AppContext(
        project_root=PROJECT_ROOT,
        assets_path=PROJECT_ROOT / "assets",
        application_version=APP_VERSION,
        logger=logging.getLogger("ui.manual"),
    )
    if args.test_data_root is not None:
        fake_registry = StorageRegistryService(FakeRegistryBackend())
        context.app_services = build_default_app_services(
            root,
            application_version=APP_VERSION,
            project_root=PROJECT_ROOT,
            registry=fake_registry,
            default_data_root=args.test_data_root.expanduser(),
        )
    app = OASKUnifiedApp(root, context=context)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
