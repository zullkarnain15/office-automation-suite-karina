"""Lightweight Windows global hotkey listener without extra dependencies."""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes


WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000
VK_F8 = 0x77


class WindowsGlobalHotkey:
    """Register one global Windows hotkey on a background message loop."""

    def __init__(
        self,
        callback: Callable[[], None],
        virtual_key: int = VK_F8,
    ) -> None:
        self.callback = callback
        self.virtual_key = virtual_key
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()
        self._error: Exception | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("Global hotkey listener is already running.")

        self._thread = threading.Thread(
            target=self._message_loop,
            name="HRISCalibrationHotkey",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(timeout=5)

        if self._error is not None:
            raise self._error
        if not self._ready.is_set():
            raise RuntimeError("Global F8 hotkey listener did not start.")

    def stop(self) -> None:
        if self._thread_id is not None:
            ctypes.windll.user32.PostThreadMessageW(
                self._thread_id,
                WM_QUIT,
                0,
                0,
            )
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = None

    def _message_loop(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = int(kernel32.GetCurrentThreadId())
        hotkey_id = 1

        if not user32.RegisterHotKey(
            None,
            hotkey_id,
            MOD_NOREPEAT,
            self.virtual_key,
        ):
            self._error = RuntimeError(
                "F8 could not be registered. Close any application using "
                "F8 as a global hotkey, then retry calibration."
            )
            self._ready.set()
            return

        self._ready.set()
        message = wintypes.MSG()
        try:
            while user32.GetMessageW(
                ctypes.byref(message),
                None,
                0,
                0,
            ) > 0:
                if message.message == WM_HOTKEY:
                    self.callback()
        finally:
            user32.UnregisterHotKey(None, hotkey_id)

    def __enter__(self) -> WindowsGlobalHotkey:
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()
