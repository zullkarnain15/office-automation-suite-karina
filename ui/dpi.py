"""Guarded Windows DPI-awareness baseline."""

from __future__ import annotations

import ctypes
import sys


def enable_dpi_awareness() -> bool:
    """Enable a conservative DPI mode before Tk creation when supported."""

    if sys.platform != "win32":
        return False
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return True
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            return True
        except (AttributeError, OSError):
            return False
