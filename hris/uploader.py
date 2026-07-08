"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : uploader.py
Module      : HRIS
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
HRIS Upload Page Handler

Sprint 6.15:
- Fill Run Control ID
- Fill start date and end date
- Attach TXT file
- Click Upload
- Confirm OK
- Click Run
- Confirm OK
- Mock-compatible for local test

=========================================================
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from time import sleep

from playwright.sync_api import Frame
from playwright.sync_api import Locator
from playwright.sync_api import Page

from hris.job_manager import HRISUploadPlanItem
from shared.logger import get_logger

logger = get_logger(__name__)

RUN_CONTROL_TEXTBOX_SCRIPT = r"""
() => {
  function isVisible(element) {
    if (!element) {
      return false;
    }
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none"
      && style.visibility !== "hidden"
      && rect.width > 0
      && rect.height > 0;
  }

  function cleanText(value) {
    return (value || "").replace(/\s+/g, " ").trim();
  }

  function mark(element) {
    if (!element) {
      return null;
    }
    for (const marked of document.querySelectorAll('[data-oask-run-control-fallback="true"]')) {
      marked.removeAttribute("data-oask-run-control-fallback");
    }
    element.setAttribute("data-oask-run-control-fallback", "true");
    return element;
  }

  const pageText = cleanText(document.body ? document.body.innerText : "");
  const looksLikeUploadSearch =
    /Attach Overtime Attendance/i.test(pageText)
    || /Overtime Upload Attendance/i.test(pageText)
    || (/Find an Existing Value/i.test(pageText) && /Run Control ID/i.test(pageText));

  if (!looksLikeUploadSearch) {
    return null;
  }

  const candidates = Array.from(document.querySelectorAll(
    'input:not([type]), input[type="text"], input.PSEDITBOX'
  )).filter(isVisible);

  for (const input of candidates) {
    const id = input.id || "";
    const name = input.name || "";
    if (/RUN_CNTL_ID/i.test(id) || /RUN_CNTL_ID/i.test(name)) {
      return mark(input);
    }
  }

  const runControlLabels = Array.from(document.querySelectorAll("label, span, div, td"))
    .filter((element) => /Run Control ID/i.test(cleanText(element.innerText || element.textContent)));

  for (const label of runControlLabels) {
    const labelRect = label.getBoundingClientRect();
    const nearby = candidates
      .map((input) => {
        const rect = input.getBoundingClientRect();
        const verticalDistance = Math.abs(rect.top - labelRect.top);
        const horizontalDistance = Math.abs(rect.left - labelRect.right);
        return { input, rect, verticalDistance, horizontalDistance };
      })
      .filter((item) => item.rect.left >= labelRect.left && item.verticalDistance <= 80)
      .sort((a, b) => (a.verticalDistance + a.horizontalDistance) - (b.verticalDistance + b.horizontalDistance));

    if (nearby.length > 0) {
      return mark(nearby[0].input);
    }
  }

  if (candidates.length === 1) {
    return mark(candidates[0]);
  }

  const bodyRect = document.body.getBoundingClientRect();
  return mark(candidates
    .filter((input) => {
      const rect = input.getBoundingClientRect();
      return rect.left > bodyRect.width * 0.20 && rect.top > 100;
    })
    .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)[0] || null);
}
"""

ADD_ATTACHMENT_OK_CLICK_SCRIPT = r"""
() => {
  function isVisible(element) {
    if (!element) {
      return false;
    }
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none"
      && style.visibility !== "hidden"
      && rect.width > 0
      && rect.height > 0;
  }

  const pageText = (document.body ? document.body.innerText : "").replace(/\s+/g, " ");
  const hasAddAttachmentMessage =
    /AddAttachment succeeded/i.test(pageText)
    || /AddAttachment\(\) call succeeded/i.test(pageText);

  if (!hasAddAttachmentMessage) {
    return false;
  }

  const candidates = Array.from(document.querySelectorAll(
    'input[name="#ICOK"], input[id="#ICOK"], input[value="OK"], button'
  )).filter(isVisible);

  const okButton = candidates.find((element) => {
    const value = element.value || "";
    const text = element.innerText || element.textContent || "";
    const name = element.name || "";
    const id = element.id || "";
    return value === "OK" || text.trim() === "OK" || name === "#ICOK" || id === "#ICOK";
  });

  if (!okButton) {
    return false;
  }

  okButton.click();
  return true;
}
"""


@dataclass(slots=True)
class HRISUploadItemResult:
    """
    Result for one HRIS TXT upload item.
    """

    success: bool
    message: str
    txt_file_name: str
    run_control_id: str
    traceback_text: str = ""


class HRISUploadPageHandler:
    """
    HRIS Upload Page Handler.

    This class handles one TXT upload action on the upload page.
    """

    def __init__(
        self,
        page: Page,
        manual_checkpoint_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.page = page
        self.manual_checkpoint_callback = manual_checkpoint_callback
        self._attachment_frame: Frame | None = None
        self._real_process_submitted = False
        self._upload_ok_confirmed = False
        self._run_requested = False
        self._scheduler_ok_confirmed = False

    def upload_one_file(
        self,
        plan_item: HRISUploadPlanItem,
        start_date: str,
        end_date: str,
    ) -> HRISUploadItemResult:
        """
        Upload one TXT file using one Run Control ID.
        """
        logger.info(
            "Uploading TXT file. File=%s, Run Control=%s",
            plan_item.txt_file_name,
            plan_item.run_control_id,
        )

        self._reset_item_state()

        txt_file_path = Path(plan_item.txt_file_path)

        if not txt_file_path.exists():
            return HRISUploadItemResult(
                success=False,
                message=f"TXT file not found: {txt_file_path}",
                txt_file_name=plan_item.txt_file_name,
                run_control_id=plan_item.run_control_id,
            )

        try:
            self._run_step_with_manual_checkpoint(
                "Run Control ID",
                lambda: self._fill_run_control_id(plan_item.run_control_id),
                (
                    "Automation belum bisa melanjutkan dari Run Control ID.\n\n"
                    "Silakan pastikan halaman Attach Overtime Attendance terbuka, "
                    "isi atau fokuskan field Run Control ID, lalu klik OK untuk "
                    "mencoba lanjut otomatis."
                ),
            )
            self._run_step_with_manual_checkpoint(
                "Isi tanggal",
                lambda: self._fill_date_range(
                    start_date=start_date,
                    end_date=end_date,
                ),
                (
                    "Automation belum menemukan field Start Date / End Date.\n\n"
                    "Silakan pastikan halaman detail Overtime Upload Attendance "
                    "sudah tampil, lalu klik OK untuk mencoba lanjut otomatis."
                ),
            )
            self._run_step_with_manual_checkpoint(
                "Attach TXT",
                lambda: self._attach_txt_file(txt_file_path),
                (
                    "Automation belum bisa membuka atau mengisi File Attachment.\n\n"
                    "Silakan klik Add Attachment atau pastikan popup File Attachment "
                    "terbuka, lalu klik OK untuk mencoba lanjut otomatis."
                ),
            )
            self._run_step_with_manual_checkpoint(
                "Klik Upload attachment",
                self._click_upload,
                (
                    "Automation belum bisa menekan tombol Upload di popup attachment.\n\n"
                    "Silakan pastikan file sudah dipilih dan tombol Upload siap, "
                    "lalu klik OK untuk mencoba lanjut otomatis."
                ),
            )
            self._run_step_with_manual_checkpoint(
                "OK AddAttachment",
                self._confirm_upload_ok,
                (
                    "Automation belum menemukan tombol OK setelah upload attachment.\n\n"
                    "Jika pesan AddAttachment succeeded muncul, biarkan terbuka lalu "
                    "klik OK di aplikasi ini untuk mencoba lanjut otomatis."
                ),
            )
            self._run_step_with_manual_checkpoint(
                "Klik Run",
                self._click_run,
                (
                    "Automation belum bisa menekan tombol Run.\n\n"
                    "Silakan pastikan halaman Overtime Upload Attendance siap dan "
                    "tombol Run terlihat, lalu klik OK untuk mencoba lanjut otomatis."
                ),
            )
            self._run_step_with_manual_checkpoint(
                "OK Process Scheduler",
                self._confirm_run_ok,
                (
                    "Automation belum menemukan tombol OK di Process Scheduler Request.\n\n"
                    "Jika dialog Process Scheduler Request sudah muncul, biarkan "
                    "terbuka lalu klik OK di aplikasi ini untuk mencoba lanjut otomatis."
                ),
            )

            if not self._verify_success():
                return HRISUploadItemResult(
                    success=False,
                    message=(
                        "Upload did not reach Process Scheduler OK "
                        "confirmation."
                    ),
                    txt_file_name=plan_item.txt_file_name,
                    run_control_id=plan_item.run_control_id,
                )

            logger.info(
                "TXT upload completed through Process Scheduler OK. File=%s",
                plan_item.txt_file_name,
            )

            return HRISUploadItemResult(
                success=True,
                message="Process Scheduler OK confirmed.",
                txt_file_name=plan_item.txt_file_name,
                run_control_id=plan_item.run_control_id,
            )

        except Exception as error:
            logger.exception(
                "TXT upload failed."
            )

            return HRISUploadItemResult(
                success=False,
                message=str(error),
                txt_file_name=plan_item.txt_file_name,
                run_control_id=plan_item.run_control_id,
                traceback_text=traceback.format_exc(),
            )

    def _fill_run_control_id(
        self,
        run_control_id: str,
    ) -> None:
        """
        Fill Run Control ID field.
        """
        if self._is_upload_form_ready():
            return

        field = self._find_first_visible_locator(
            [
                "#PRCSRUNCNTL_RUN_CNTL_ID",
                "[name='PRCSRUNCNTL_RUN_CNTL_ID']",
                "input[id*='RUN_CNTL_ID']",
                "input[name*='RUN_CNTL_ID']",
                "#run_control_id",
            ],
            fallback_handle_script=RUN_CONTROL_TEXTBOX_SCRIPT,
        )
        field.wait_for(state="visible", timeout=10_000)
        field.fill(run_control_id)

        if self._locator_exists("#PRCSRUNCNTL_RUN_CNTL_ID") or self._locator_exists(
            "input[name*='RUN_CNTL_ID']"
        ):
            field.press("Enter")
            try:
                self._wait_for_upload_form_ready(timeout=15_000)
            except Exception:
                search_button = self._find_first_visible_locator(
                    [
                        "#PTS_CFG_CL_WRK_PTS_SRCH_BTN",
                        "[name='PTS_CFG_CL_WRK_PTS_SRCH_BTN']",
                        "input[value='Search']",
                        "button:has-text('Search')",
                    ],
                    timeout=10_000,
                )
                self._click_visible_locator(search_button)
                self._wait_for_upload_form_ready(timeout=30_000)

    def _fill_date_range(
        self,
        start_date: str,
        end_date: str,
    ) -> None:
        """
        Fill start date and end date fields.
        """
        start_date_field = self._find_first_visible_locator(
            [
                "#IDOT_UPLOAD_ATT_START_DATE",
                "[name='IDOT_UPLOAD_ATT_START_DATE']",
                "input[id*='START_DATE']",
                "input[name*='START_DATE']",
                "#start_date",
            ],
        )
        end_date_field = self._find_first_visible_locator(
            [
                "#IDOT_UPLOAD_ATT_END_DATE",
                "[name='IDOT_UPLOAD_ATT_END_DATE']",
                "input[id*='END_DATE']",
                "input[name*='END_DATE']",
                "#end_date",
            ],
        )

        start_date_field.wait_for(state="visible", timeout=10_000)
        end_date_field.wait_for(state="visible", timeout=10_000)

        start_date_field.fill(start_date)
        end_date_field.fill(end_date)

    def _attach_txt_file(
        self,
        txt_file_path: Path,
    ) -> None:
        """
        Attach TXT file.
        """
        mock_file_input = self.page.locator("#attachment_file")

        if self._is_attached(mock_file_input):
            mock_file_input.set_input_files(str(txt_file_path))
            return

        self._attachment_frame = self._try_find_frame_with_selector(
            "input[name='#ICOrigFileName']",
            state="attached",
            timeout=1_000,
        )

        if self._attachment_frame is not None:
            file_input = self._attachment_frame.locator(
                "input[name='#ICOrigFileName']"
            )
            file_input.set_input_files(str(txt_file_path))
            return

        self._click_visible_locator(
            self._find_first_visible_locator(
                [
                    "#IDOT_UPLOAD_ATT_ATTACHADD",
                    "[name='IDOT_UPLOAD_ATT_ATTACHADD']",
                    "input[id*='ATTACHADD']",
                    "input[name*='ATTACHADD']",
                ],
            )
        )

        self._attachment_frame = self._find_frame_with_selector(
            "input[name='#ICOrigFileName']",
            state="attached",
            timeout=30_000,
        )

        file_input = self._attachment_frame.locator(
            "input[name='#ICOrigFileName']"
        )
        file_input.wait_for(state="attached", timeout=10_000)
        file_input.set_input_files(str(txt_file_path))

    def _click_upload(self) -> None:
        """
        Click Upload button.
        """
        if self._is_any_visible(
            [
                "input[name='#ICOK']",
                "input[id='#ICOK']",
                "#upload_ok_button",
            ]
        ):
            return

        if self._attachment_frame is not None:
            upload_button = self._attachment_frame.locator("#Upload")
            upload_button.wait_for(state="visible", timeout=10_000)

            try:
                upload_button.click(timeout=10_000)
            except Exception:
                self._attachment_frame.evaluate(
                    "() => { const button = document.querySelector('#Upload');"
                    " if (button) { button.disabled = false; button.click(); } }"
                )
            return

        self._click_visible_locator(
            self.page.locator("#upload_button"),
        )

    def _confirm_upload_ok(self) -> None:
        """
        Confirm Upload OK.
        """
        if self._is_any_visible(
            [
                "#PRCSRQSTDLG_WRK_LOADPRCSRQSTDLGPB",
                "[name='PRCSRQSTDLG_WRK_LOADPRCSRQSTDLGPB']",
                "#run_button",
                "input[name='#ICSave']",
            ]
        ):
            self._upload_ok_confirmed = True
            if self._is_any_visible(["input[name='#ICSave']"]):
                self._run_requested = True
            return

        try:
            ok_button = self._find_first_visible_locator(
                [
                    "input[name='#ICOK']",
                    "input[id='#ICOK']",
                    "input[value='OK']",
                    "button:has-text('OK')",
                    "#upload_ok_button",
                ],
                timeout=10_000,
            )
            self._click_visible_locator(
                ok_button,
            )
        except Exception:
            if not self._click_add_attachment_ok_with_script():
                raise

        self._wait_for_any_visible(
            [
                "#PRCSRQSTDLG_WRK_LOADPRCSRQSTDLGPB",
                "[name='PRCSRQSTDLG_WRK_LOADPRCSRQSTDLGPB']",
                "#run_button",
                "input[name='#ICSave']",
            ],
            timeout=30_000,
        )
        self._upload_ok_confirmed = True
        if self._is_any_visible(["input[name='#ICSave']"]):
            self._run_requested = True

    def _click_run(self) -> None:
        """
        Click Run button.
        """
        process_frame = self._try_find_frame_with_selector(
            "input[name='#ICSave']",
            state="visible",
            timeout=1_000,
        )

        if process_frame is not None:
            self._upload_ok_confirmed = True
            self._run_requested = True
            return

        run_button = self._find_first_visible_locator(
            [
                "#PRCSRQSTDLG_WRK_LOADPRCSRQSTDLGPB",
                "[name='PRCSRQSTDLG_WRK_LOADPRCSRQSTDLGPB']",
                "#run_button",
            ],
            timeout=20_000,
        )
        self._click_visible_locator(
            run_button,
        )
        self._run_requested = True
        self._wait_for_any_visible(
            [
                "input[name='#ICSave']",
                "#run_ok_button",
            ],
            timeout=30_000,
        )

    def _confirm_run_ok(self) -> None:
        """
        Confirm Run OK.
        """
        if not self._run_requested:
            raise RuntimeError(
                "Process Scheduler OK cannot be confirmed before Run is clicked."
            )

        mock_run_ok = self.page.locator("#run_ok_button")

        if self._is_visible(mock_run_ok):
            self._click_visible_locator(mock_run_ok)
            self._scheduler_ok_confirmed = True
            return

        try:
            process_frame = self._find_frame_with_selector(
                "input[name='#ICSave']",
                state="visible",
                timeout=30_000,
            )
            self._click_visible_locator(
                process_frame.locator("input[name='#ICSave']")
            )
            self._real_process_submitted = True
            self._scheduler_ok_confirmed = True
            return
        except Exception:
            logger.info(
                "PeopleSoft Process Scheduler OK was not found. Trying mock OK."
            )

        self._click_visible_locator(
            self.page.locator("#run_ok_button"),
        )
        self._scheduler_ok_confirmed = True

    def _verify_success(self) -> bool:
        """
        Verify success marker.
        """
        if not (
            self._upload_ok_confirmed
            and self._run_requested
            and self._scheduler_ok_confirmed
        ):
            return False

        if self._real_process_submitted:
            return True

        success_marker = self.page.locator("#success_message")

        try:
            success_marker.wait_for(
                state="visible",
                timeout=5_000,
            )
            return True
        except Exception:
            return False

    def _reset_item_state(self) -> None:
        """
        Reset per-file upload state before processing an item.
        """
        self._attachment_frame = None
        self._real_process_submitted = False
        self._upload_ok_confirmed = False
        self._run_requested = False
        self._scheduler_ok_confirmed = False

    def _run_step_with_manual_checkpoint(
        self,
        step_name: str,
        action: Callable[[], None],
        checkpoint_message: str,
    ) -> None:
        """
        Run one named upload step and preserve the step name on failure.
        """
        logger.info("HRIS upload step started: %s", step_name)

        try:
            self._run_with_manual_checkpoint(
                action=action,
                checkpoint_message=checkpoint_message,
            )
        except Exception as error:
            raise RuntimeError(
                f"HRIS upload stopped at step '{step_name}': {error}"
            ) from error

        logger.info("HRIS upload step completed: %s", step_name)

    def _run_with_manual_checkpoint(
        self,
        action: Callable[[], None],
        checkpoint_message: str,
    ) -> None:
        """
        Run an upload step, then offer one manual checkpoint retry if it fails.
        """
        try:
            action()
            return
        except Exception as first_error:
            if self.manual_checkpoint_callback is None:
                raise

            logger.warning(
                "HRIS upload step needs manual checkpoint: %s",
                first_error,
            )

            self.manual_checkpoint_callback(
                f"{checkpoint_message}\n\nDetail error:\n{first_error}"
            )

        action()

    def _click_add_attachment_ok_with_script(self) -> bool:
        """
        Click PeopleSoft AddAttachment success OK with a DOM fallback.
        """
        deadline = monotonic() + 10

        while monotonic() < deadline:
            for scope in self._locator_scopes():
                try:
                    clicked = bool(scope.evaluate(ADD_ATTACHMENT_OK_CLICK_SCRIPT))
                except Exception:
                    continue

                if clicked:
                    return True

            sleep(0.25)

        return False

    def _find_first_visible_locator(
        self,
        selectors: list[str],
        timeout: int = 10_000,
        fallback_handle_script: str | None = None,
    ) -> Locator:
        """
        Return the first visible locator from the current page.
        """
        deadline = monotonic() + timeout / 1000
        last_error: Exception | None = None

        while monotonic() < deadline:
            for selector in selectors:
                for scope in self._locator_scopes():
                    locator = scope.locator(selector).first

                    try:
                        locator.wait_for(
                            state="visible",
                            timeout=250,
                        )
                        return locator
                    except Exception as error:
                        last_error = error

            if fallback_handle_script is not None:
                fallback_locator = self._find_locator_by_handle_script(
                    fallback_handle_script,
                )

                if fallback_locator is not None:
                    return fallback_locator

            sleep(0.1)

        raise RuntimeError(
            f"Required HRIS element was not found. Selectors={selectors}. "
            f"Last error={last_error}"
        )

    def _find_locator_by_handle_script(
        self,
        script: str,
    ) -> Locator | None:
        """
        Return a locator for an element found by a JS handle script.
        """
        for scope in self._locator_scopes():
            try:
                scope.evaluate(script)
            except Exception:
                continue

            locator = scope.locator(
                '[data-oask-run-control-fallback="true"]'
            ).first

            if self._is_visible(locator):
                return locator

        return None

    def _find_frame_with_selector(
        self,
        selector: str,
        state: str = "visible",
        timeout: int = 10_000,
    ) -> Frame:
        """
        Find the first frame containing a target selector.
        """
        deadline = monotonic() + timeout / 1000
        last_error: Exception | None = None

        while monotonic() < deadline:
            for frame in self.page.frames:
                locator = frame.locator(selector).first

                try:
                    locator.wait_for(
                        state=state,
                        timeout=250,
                    )
                    return frame
                except Exception as error:
                    last_error = error

            sleep(0.1)

        raise RuntimeError(
            f"Required HRIS frame element was not found. Selector={selector}. "
            f"Last error={last_error}"
        )

    def _try_find_frame_with_selector(
        self,
        selector: str,
        state: str = "visible",
        timeout: int = 1_000,
    ) -> Frame | None:
        """
        Return a frame containing a selector, or None when not found.
        """
        try:
            return self._find_frame_with_selector(
                selector=selector,
                state=state,
                timeout=timeout,
            )
        except Exception:
            return None

    def _wait_for_any_visible(
        self,
        selectors: list[str],
        timeout: int = 10_000,
    ) -> None:
        """
        Wait until at least one selector becomes visible.
        """
        self._find_first_visible_locator(
            selectors=selectors,
            timeout=timeout,
        )

    def _wait_for_upload_form_ready(
        self,
        timeout: int = 10_000,
    ) -> None:
        """
        Wait until the PeopleSoft upload form is visible.
        """
        self._wait_for_any_visible(
            [
                "#IDOT_UPLOAD_ATT_START_DATE",
                "[name='IDOT_UPLOAD_ATT_START_DATE']",
                "#IDOT_UPLOAD_ATT_ATTACHADD",
                "[name='IDOT_UPLOAD_ATT_ATTACHADD']",
                "input[id*='START_DATE']",
                "input[name*='START_DATE']",
                "input[id*='ATTACHADD']",
                "input[name*='ATTACHADD']",
            ],
            timeout=timeout,
        )

    def _is_upload_form_ready(self) -> bool:
        """
        Return True when the upload form after Run Control search is ready.
        """
        try:
            self._wait_for_upload_form_ready(timeout=1_000)
            return True
        except Exception:
            return False

    def _is_any_visible(
        self,
        selectors: list[str],
    ) -> bool:
        """
        Return True when any selector is visible in page or frames.
        """
        for selector in selectors:
            for scope in self._locator_scopes():
                if self._is_visible(scope.locator(selector).first):
                    return True

        return False

    def _locator_exists(
        self,
        selector: str,
    ) -> bool:
        """
        Return True when a selector is attached to the page.
        """
        for scope in self._locator_scopes():
            locator = scope.locator(selector).first

            if self._is_attached(locator):
                return True

        return False

    def _locator_scopes(self) -> list[Page | Frame]:
        """
        Return page and frame scopes for PeopleSoft DOM lookup.
        """
        return [self.page, *self.page.frames]

    @staticmethod
    def _is_attached(
        locator: Locator,
    ) -> bool:
        """
        Return True when a locator exists in the DOM.
        """
        try:
            locator.wait_for(
                state="attached",
                timeout=250,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _is_visible(
        locator: Locator,
    ) -> bool:
        """
        Return True when a locator is visible.
        """
        try:
            locator.wait_for(
                state="visible",
                timeout=250,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _click_visible_locator(
        locator: Locator,
    ) -> None:
        """
        Wait for a clickable element before clicking it.
        """
        locator.wait_for(
            state="visible",
            timeout=10_000,
        )
        locator.click()
