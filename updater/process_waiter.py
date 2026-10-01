"""Process wait helpers using only the Python standard library."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def is_process_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _is_process_running_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        if sys.platform == "win32":
            completed = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                check=False,
            )
            return str(pid) in completed.stdout
        return False
    return True


def _is_process_running_windows(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    exit_code = wintypes.DWORD()
    try:
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def wait_for_exit(pid: int | None, timeout_seconds: float) -> bool:
    if pid is None:
        return True
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not is_process_running(pid):
            return True
        time.sleep(0.25)
    return not is_process_running(pid)


def request_graceful_exit(pid: int | None) -> None:
    if pid is None or not is_process_running(pid):
        return
    if sys.platform != "win32":
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return
