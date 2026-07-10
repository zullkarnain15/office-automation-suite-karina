"""Lightweight text-based verification for assisted HRIS submissions."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from shared.config_manager import HRISConfiguration
from shared.logger import get_logger

logger = get_logger(__name__)

DEFAULT_SUCCESS_TEXTS = ("Process Instance", "Submitted", "Queued")
DEFAULT_FAILURE_TEXTS = ("Error", "Invalid", "Failed")
PROCESS_INSTANCE_PATTERN = re.compile(
    r"process\s+instance\s*[:#]?\s*(\d+)",
    flags=re.IGNORECASE,
)


@dataclass(slots=True)
class HRISAssistedVerificationResult:
    status: str
    message: str
    matched_text: str = ""
    process_instance: str = ""

    @property
    def submitted(self) -> bool:
        return self.status == "SUBMITTED"


class HRISAssistedResultVerifier:
    def __init__(
        self,
        page: Any,
        configuration: HRISConfiguration,
        manual_callback: Callable[[str], str] | None = None,
    ) -> None:
        self.page = page
        self.configuration = configuration
        self.manual_callback = manual_callback
        upload = configuration.upload
        self.enabled = self._to_bool(
            upload.get("Assisted_Verification_Enabled", True)
        )
        self.manual_on_unknown = self._to_bool(
            upload.get("Manual_Verification_On_Unknown", True)
        )
        self.manual_on_error = self._to_bool(
            upload.get("Manual_Verification_On_Error", True)
        )
        self.initial_wait = self._to_float(
            upload.get("Verification_Wait_Seconds", 1),
            1,
        )
        self.timeout = self._to_float(
            upload.get("Verification_Timeout_Seconds", 10),
            10,
        )
        self.poll_seconds = self._to_float(
            upload.get("Verification_Poll_Seconds", 1),
            1,
        )
        self.success_texts = self._phrases(
            upload.get("Verification_Success_Texts"),
            DEFAULT_SUCCESS_TEXTS,
        )
        self.failure_texts = self._phrases(
            upload.get("Verification_Failure_Texts"),
            DEFAULT_FAILURE_TEXTS,
        )

    def verify_item(self, plan_item: Any) -> HRISAssistedVerificationResult:
        if not self.enabled:
            return self._manual_decision(
                plan_item,
                "Automatic verification is disabled.",
            )

        time.sleep(max(0.0, self.initial_wait))
        while True:
            result = self._scan_until_deadline()
            if result.status == "SUBMITTED":
                return result
            if result.status == "FAILED":
                if not self.manual_on_error:
                    return result
                manual_result = self._manual_decision(
                    plan_item,
                    result.message,
                )
                if manual_result.status == "RETRY":
                    continue
                return manual_result
            if not self.manual_on_unknown:
                return HRISAssistedVerificationResult(
                    "FAILED",
                    "HRIS result could not be verified automatically.",
                )
            manual_result = self._manual_decision(
                plan_item,
                (
                    "No configured success or failure message was found "
                    "on the HRIS page."
                ),
            )
            if manual_result.status == "RETRY":
                continue
            return manual_result

    def _scan_until_deadline(self) -> HRISAssistedVerificationResult:
        deadline = time.monotonic() + max(0.0, self.timeout)
        while True:
            page_text = self._read_page_text()
            result = self._classify(page_text)
            if result.status != "UNKNOWN":
                return result
            if time.monotonic() >= deadline:
                return result
            time.sleep(max(0.1, self.poll_seconds))

    def _read_page_text(self) -> str:
        texts: list[str] = []
        for frame in getattr(self.page, "frames", []):
            try:
                text = frame.locator("body").inner_text(timeout=2_000)
            except Exception as error:
                logger.debug("Verification frame text unavailable: %s", error)
                continue
            if text:
                texts.append(str(text))
        return "\n".join(texts)

    def _classify(self, page_text: str) -> HRISAssistedVerificationResult:
        normalized = page_text.casefold()
        for phrase in self.failure_texts:
            if phrase.casefold() in normalized:
                return HRISAssistedVerificationResult(
                    "FAILED",
                    f"HRIS failure message detected: {phrase}",
                    matched_text=phrase,
                )
        for phrase in self.success_texts:
            if phrase.casefold() in normalized:
                process_match = PROCESS_INSTANCE_PATTERN.search(page_text)
                process_instance = (
                    process_match.group(1) if process_match else ""
                )
                message = f"HRIS submission verified: {phrase}"
                if process_instance:
                    message += f" (Process Instance {process_instance})"
                return HRISAssistedVerificationResult(
                    "SUBMITTED",
                    message,
                    matched_text=phrase,
                    process_instance=process_instance,
                )
        return HRISAssistedVerificationResult(
            "UNKNOWN",
            "No configured HRIS result text detected.",
        )

    def _manual_decision(
        self,
        plan_item: Any,
        reason: str,
    ) -> HRISAssistedVerificationResult:
        prompt = (
            f"{reason}\n\n"
            f"File: {getattr(plan_item, 'txt_file_name', '')}\n"
            f"Run Control ID: {getattr(plan_item, 'run_control_id', '')}\n\n"
            "Inspect the HRIS page, then choose Confirm Submitted, "
            "Mark Failed, Retry Verification, or Stop Batch."
        )
        if self.manual_callback is not None:
            action = self.manual_callback(prompt)
        else:
            action = input(
                f"{prompt}\nType submitted/failed/retry/stop: "
            ).strip().lower()

        if action == "submitted":
            return HRISAssistedVerificationResult(
                "SUBMITTED",
                "HRIS submission confirmed manually by operator.",
            )
        if action == "retry":
            return HRISAssistedVerificationResult(
                "RETRY",
                "Operator requested verification retry.",
            )
        if action == "failed":
            return HRISAssistedVerificationResult(
                "FAILED",
                "HRIS submission marked failed by operator.",
            )
        return HRISAssistedVerificationResult(
            "STOPPED",
            "HRIS batch stopped by operator during verification.",
        )

    @staticmethod
    def _phrases(
        value: Any,
        defaults: tuple[str, ...],
    ) -> tuple[str, ...]:
        if value is None or not str(value).strip():
            return defaults
        phrases = tuple(
            phrase.strip()
            for phrase in str(value).split("|")
            if phrase.strip()
        )
        return phrases or defaults

    @staticmethod
    def _to_bool(value: Any) -> bool:
        return str(value).strip().lower() in {"true", "1", "yes", "y"}

    @staticmethod
    def _to_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
