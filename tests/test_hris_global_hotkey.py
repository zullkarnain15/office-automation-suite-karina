import ctypes
import sys
import threading

import pytest

from hris.global_hotkey import VK_F8, WindowsGlobalHotkey


@pytest.mark.skipif(sys.platform != "win32", reason="Windows hotkey only")
def test_global_f8_hotkey_callback() -> None:
    captured = threading.Event()

    with WindowsGlobalHotkey(captured.set):
        ctypes.windll.user32.keybd_event(VK_F8, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_F8, 0, 0x0002, 0)
        assert captured.wait(timeout=2)
