"""Small, Windows-only ICMP probe with no raw sockets or administrator rights."""

from __future__ import annotations

import ipaddress
import subprocess
import time
from dataclasses import dataclass
from threading import Event
from typing import Callable


@dataclass(frozen=True, slots=True)
class PingProbeResult:
    status: str
    ip_address: str
    latency_ms: int | None = None
    exit_code: int | None = None
    diagnostic: str = ""


class WindowsPingEngine:
    """Run exactly one standard Windows ICMP echo request per invocation."""

    def __init__(self, *, popen: Callable = subprocess.Popen, clock: Callable[[], float] = time.monotonic) -> None:
        self.popen = popen
        self.clock = clock

    def probe(self, ip_address: str, timeout_ms: int, cancel_event: Event | None = None) -> PingProbeResult:
        address = self._validate_ipv4(ip_address)
        if not 100 <= int(timeout_ms) <= 60_000:
            raise ValueError("Ping timeout harus 100..60000 ms.")
        if cancel_event is not None and cancel_event.is_set():
            return PingProbeResult("CANCELLED", address, diagnostic="CANCELLED_BEFORE_START")
        command = ["ping.exe", "-n", "1", "-w", str(int(timeout_ms)), address]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        started = self.clock()
        try:
            process = self.popen(
                command,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="oem",
                errors="replace",
                creationflags=flags,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return PingProbeResult("ERROR", address, diagnostic=f"PING_START_FAILED: {exc}")

        deadline = started + (int(timeout_ms) / 1000.0) + 1.0
        output = ""
        while True:
            if cancel_event is not None and cancel_event.is_set():
                self._terminate(process)
                return PingProbeResult("CANCELLED", address, diagnostic="CANCELLED_DURING_PING")
            remaining = deadline - self.clock()
            if remaining <= 0:
                self._terminate(process)
                return PingProbeResult("UNKNOWN", address, diagnostic="PING_PROCESS_TIMEOUT")
            try:
                output, _ = process.communicate(timeout=min(0.10, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
            except (OSError, subprocess.SubprocessError) as exc:
                self._terminate(process)
                return PingProbeResult("ERROR", address, diagnostic=f"PING_PROCESS_FAILED: {exc}")

        elapsed_ms = max(0, round((self.clock() - started) * 1000))
        exit_code = process.returncode
        return self._classify(address, exit_code, output or "", elapsed_ms)

    @staticmethod
    def _validate_ipv4(value: str) -> str:
        try:
            parsed = ipaddress.ip_address(value.strip())
        except ValueError as exc:
            raise ValueError("IP address harus IPv4 valid.") from exc
        if parsed.version != 4:
            raise ValueError("Ping engine Sprint 3 hanya mendukung IPv4.")
        return str(parsed)

    @staticmethod
    def _terminate(process) -> None:
        try:
            process.terminate()
            process.communicate(timeout=0.5)
        except Exception:
            try:
                process.kill()
                process.communicate(timeout=0.5)
            except Exception:
                pass

    @staticmethod
    def _classify(address: str, exit_code: int | None, output: str, elapsed_ms: int) -> PingProbeResult:
        normalized = output.casefold()
        if exit_code == 0:
            return PingProbeResult("ONLINE", address, elapsed_ms, exit_code)
        unreachable = (
            "destination host unreachable", "destination net unreachable",
            "destination unreachable", "general failure", "transmit failed",
        )
        if any(token in normalized for token in unreachable):
            return PingProbeResult("NETWORK_UNREACHABLE", address, None, exit_code, output.strip()[:1000])
        if "request timed out" in normalized or "timed out" in normalized:
            return PingProbeResult("OFFLINE", address, None, exit_code, output.strip()[:1000])
        return PingProbeResult("UNKNOWN", address, None, exit_code, output.strip()[:1000] or "PING_UNCLASSIFIED")
