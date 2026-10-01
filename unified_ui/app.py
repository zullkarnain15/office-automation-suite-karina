"""Executable entry point for the OAS-K Unified UI shell."""

from __future__ import annotations

import tkinter as tk

from shared.logger import get_logger
from unified_ui.main_window import MainWindow

logger = get_logger(__name__)


def create_app() -> tuple[tk.Tk, MainWindow]:
    """Create the Tk root and Unified UI main window."""

    root = tk.Tk()
    window = MainWindow(root)
    return root, window


def main() -> None:
    """Start the Unified UI event loop."""

    logger.info("Starting OAS-K Unified UI shell.")
    root, _window = create_app()
    root.mainloop()


if __name__ == "__main__":
    main()
