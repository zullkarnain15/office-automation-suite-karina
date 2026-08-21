from __future__ import annotations

import subprocess
import sys
import time

from updater.process_waiter import wait_for_exit


def test_old_process_wait_success() -> None:
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    assert wait_for_exit(process.pid, 5)


def test_old_process_timeout() -> None:
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
    try:
        assert not wait_for_exit(process.pid, 0.1)
    finally:
        process.terminate()
        process.wait(timeout=5)
