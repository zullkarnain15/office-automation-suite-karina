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

MESSAGE_OK_CLICK_SCRIPT = r"""
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

  const pageText = cleanText(document.body ? document.body.innerText : "");
  const hasUploadMessage =
    /Message/i.test(pageText)
    || /AddAttachment/i.test(pageText)
    || /succeeded/i.test(pageText)
    || /success/i.test(pageText);

  if (!hasUploadMessage) {
    return false;
  }

  const candidates = Array.from(document.querySelectorAll(
    'input[name*="ICOK"], input[id*="ICOK"], input[value], button, a'
  )).filter(isVisible);

  const okButton = candidates.find((element) => {
    const value = cleanText(element.value);
    const text = cleanText(element.innerText || element.textContent);
    const title = cleanText(element.getAttribute("title"));
    const name = element.name || "";
    const id = element.id || "";
    return value === "OK"
      || text === "OK"
      || title === "OK"
      || /ICOK/i.test(name)
      || /ICOK/i.test(id);
  });

  if (!okButton) {
    return false;
  }

  okButton.click();
  return true;
}
"""

RUN_BUTTON_SELECTORS = [
    "#PRCSRQSTDLG_WRK_LOADPRCSRQSTDLGPB",
    "[name='PRCSRQSTDLG_WRK_LOADPRCSRQSTDLGPB']",
    "#IDOT_UPLOAD_ATT_RUN",
    "#IDOT_UPLOAD_ATT_RUN_PB",
    "[name='IDOT_UPLOAD_ATT_RUN']",
    "[name='IDOT_UPLOAD_ATT_RUN_PB']",
    "input[id*='RUN_PB']",
    "input[name*='RUN_PB']",
    "input[type='button'][value='Run']",
    "input[type='submit'][value='Run']",
    "input[value=' Run ']",
    "input[value*='Run']",
    "input[title='Run']",
    "input[title*='Run']",
    "button:has-text('Run')",
    "a:has-text('Run')",
    "#run_button",
]

RUN_CLICK_SCRIPT = r"""
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

  const candidates = Array.from(document.querySelectorAll(
    'input, button, a, span, div'
  )).filter(isVisible);

  const runButton = candidates.find((element) => {
    const value = cleanText(element.value);
    const text = cleanText(element.innerText || element.textContent);
    const title = cleanText(element.getAttribute("title"));
    const id = element.id || "";
    const name = element.name || "";
    return value === "Run"
      || text === "Run"
      || title === "Run"
      || /LOADPRCSRQSTDLGPB/i.test(id)
      || /LOADPRCSRQSTDLGPB/i.test(name)
      || /RUN_PB/i.test(id)
      || /RUN_PB/i.test(name);
  });

  if (!runButton) {
    return false;
  }

  runButton.click();
  return true;
}
"""

FILENAME_POPULATED_SCRIPT = r"""
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

  const filenameLabels = Array.from(document.querySelectorAll("label, span, div, td"))
    .filter((element) => /Filename/i.test(cleanText(element.innerText || element.textContent)));

  for (const label of filenameLabels) {
    const labelRect = label.getBoundingClientRect();
    const nearbyInputs = Array.from(document.querySelectorAll("input"))
      .filter(isVisible)
      .filter((input) => (input.type || "").toLowerCase() !== "file")
      .filter((input) => !/ICOrigFileName/i.test(input.id || ""))
      .filter((input) => !/ICOrigFileName/i.test(input.name || ""))
      .map((input) => {
        const rect = input.getBoundingClientRect();
        return {
          input,
          rect,
          verticalDistance: Math.abs(rect.top - labelRect.top),
          horizontalDistance: Math.abs(rect.left - labelRect.right),
        };
      })
      .filter((item) => item.rect.left >= labelRect.left && item.verticalDistance <= 80)
      .sort((a, b) => (a.verticalDistance + a.horizontalDistance) - (b.verticalDistance + b.horizontalDistance));

    if (nearbyInputs.some((item) => cleanText(item.input.value))) {
      return true;
    }
  }

  return false;
}
"""

ADD_ATTACHMENT_CLICK_SCRIPT = r"""
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

  const candidates = Array.from(document.querySelectorAll(
    'input, button, a, span, div'
  )).filter(isVisible);

  const addButton = candidates.find((element) => {
    const value = cleanText(element.value);
    const text = cleanText(element.innerText || element.textContent);
    const title = cleanText(element.getAttribute("title"));
    const id = element.id || "";
    const name = element.name || "";
    return value === "Add Attachment"
      || text === "Add Attachment"
      || title === "Add Attachment"
      || /ATTACHADD/i.test(id)
      || /ATTACHADD/i.test(name);
  });

  if (!addButton) {
    return false;
  }

  if (typeof window.submitAction_win0 === "function" && document.win0) {
    window.submitAction_win0(document.win0, addButton.id || addButton.name, new Event("click"));
    return true;
  }

  addButton.click();
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
        post_upload_recorder_callback: (
            Callable[[HRISUploadPlanItem, str, str], object] | None
        ) = None,
    ) -> None:
        self.page = page
        self.manual_checkpoint_callback = manual_checkpoint_callback
        self.post_upload_recorder_callback = post_upload_recorder_callback
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
            if self.post_upload_recorder_callback is not None:
                self._wait_for_post_upload_macro_ready(timeout=10_000)
                recorder_result = self.post_upload_recorder_callback(
                    plan_item,
                    start_date,
                    end_date,
                )
                if not bool(getattr(recorder_result, "success", False)):
                    raise RuntimeError(
                        str(
                            getattr(
                                recorder_result,
                                "message",
                                "Recorder gagal setelah upload.",
                            )
                        )
                    )
                self._upload_ok_confirmed = True
                self._run_requested = True
                self._scheduler_ok_confirmed = True
            else:
                self._run_playwright_post_upload_steps()

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

    def _run_playwright_post_upload_steps(self) -> None:
        """Finish the upload with Playwright when recorder mode is disabled."""
        self._run_step_with_manual_checkpoint(
            "OK AddAttachment",
            self._confirm_upload_ok,
            (
                "Automation belum menemukan tombol OK setelah upload attachment.\n\n"
                "Jika pesan AddAttachment succeeded muncul, biarkan terbuka lalu "
                "klik OK di aplikasi ini untuk mencoba lanjut otomatis."
            ),
        )

    def _wait_for_post_upload_macro_ready(
        self,
        timeout: int = 10_000,
    ) -> None:
        """
        Wait briefly for the post-upload OK surface before coordinate replay.
        """
        try:
            self._wait_for_any_visible(
                [
                    "input[name='#ICOK']",
                    "input[id='#ICOK']",
                    "input[value='OK']",
                    "button:has-text('OK')",
                    "#upload_ok_button",
                ],
                timeout=timeout,
            )
        except Exception:
            logger.info(
                "Post-upload OK was not detected before macro replay; continuing."
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
        field.focus()
        field.fill(run_control_id)

        if self._is_upload_form_ready():
            return

        search_button = self._find_first_visible_locator(
            [
                "#PTS_CFG_CL_WRK_PTS_SRCH_BTN",
                "[name='PTS_CFG_CL_WRK_PTS_SRCH_BTN']",
                "#SEARCH",
                "[name='SEARCH']",
                "input[id*='SEARCH']",
                "input[name*='SEARCH']",
                "input[value='Search']",
                "button:text-is('Search')",
                "a:text-is('Search')",
            ],
            timeout=10_000,
        )
        self._click_visible_locator(search_button)
        self._wait_for_upload_form_ready(timeout=30_000)

    def _offer_assisted_upload_checkpoint(
        self,
        plan_item: HRISUploadPlanItem,
        txt_file_path: Path,
    ) -> None:
        """
        Pause at the risky upload point so the operator can help if needed.
        """
        if self.manual_checkpoint_callback is None:
            return

        self.manual_checkpoint_callback(
            (
                "Assisted Mode aktif.\n\n"
                "Tanggal sudah terisi. Ini titik rawan PeopleSoft.\n\n"
                "Pilihan aman:\n"
                "1. Jika tampilan browser normal, langsung klik OK di aplikasi "
                "ini agar automation lanjut otomatis.\n"
                "2. Jika browser terlihat nyari-nyari/geser-geser, bantu manual "
                "di browser sampai salah satu kondisi ini terlihat:\n"
                "- File Attachment popup terbuka, atau\n"
                "- Filename sudah terisi, atau\n"
                "- Message AddAttachment succeeded masih terbuka, atau\n"
                "- Tombol Run terlihat setelah Message OK.\n\n"
                "Setelah itu kembali ke aplikasi ini dan klik OK. Automation akan "
                "lanjut dari posisi halaman sekarang, bukan membuka menu ulang.\n\n"
                f"File yang diproses: {plan_item.txt_file_name}\n"
                f"Path: {txt_file_path}"
            )
        )

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

        start_date_field.focus()
        start_date_field.fill(start_date)
        end_date_field.focus()
        end_date_field.fill(end_date)

        self._assert_field_value(
            locator=start_date_field,
            expected_value=start_date,
            field_name="Start Date",
        )
        self._assert_field_value(
            locator=end_date_field,
            expected_value=end_date,
            field_name="End Date",
        )

    def _attach_txt_file(
        self,
        txt_file_path: Path,
    ) -> None:
        """
        Attach TXT file.
        """
        if self._is_add_attachment_success_visible() or self._is_filename_populated():
            return

        mock_file_input = self.page.locator("#attachment_file")

        if self._is_attached(mock_file_input):
            self._set_attachment_file_input(mock_file_input, txt_file_path)
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
            self._set_attachment_file_input(
                file_input,
                txt_file_path,
                self._attachment_frame,
            )
            return

        page_file_input = self._find_attachment_file_input_on_page(
            timeout=1_000,
        )

        if page_file_input is not None:
            self._set_attachment_file_input(page_file_input, txt_file_path)
            return

        add_attachment_button = self._find_first_visible_locator(
            [
                "#IDOT_UPLOAD_ATT_ATTACHADD",
                "[name='IDOT_UPLOAD_ATT_ATTACHADD']",
                "input[id*='ATTACHADD']",
                "input[name*='ATTACHADD']",
                "input[value='Add Attachment']",
                "input[value*='Add Attachment']",
                "input[title='Add Attachment']",
                "input[title*='Add Attachment']",
                "button:has-text('Add Attachment')",
                "a:has-text('Add Attachment')",
            ],
            timeout=20_000,
        )

        self._click_add_attachment_button(add_attachment_button)

        page_file_input = self._find_attachment_file_input_on_page(
            timeout=2_000,
        )

        if page_file_input is not None:
            self._set_attachment_file_input(page_file_input, txt_file_path)
            return

        self._attachment_frame = self._find_frame_with_selector(
            "input[type='file']",
            state="attached",
            timeout=30_000,
        )

        file_input = self._attachment_frame.locator(
            "input[name='#ICOrigFileName'], input[type='file']"
        ).first
        file_input.wait_for(state="attached", timeout=10_000)
        self._set_attachment_file_input(
            file_input,
            txt_file_path,
            self._attachment_frame,
        )

    def _click_add_attachment_button(
        self,
        add_attachment_button: Locator,
    ) -> None:
        """
        Click Add Attachment and wait for the PeopleSoft attachment dialog.
        """
        click_attempts = [
            lambda: self._click_visible_locator(add_attachment_button),
            lambda: add_attachment_button.click(force=True, timeout=5_000),
            lambda: self._click_visible_locator_by_mouse(add_attachment_button),
            lambda: self._click_add_attachment_with_script(timeout_seconds=5),
        ]

        for click_attempt in click_attempts:
            try:
                click_attempt()
            except Exception:
                continue

            if self._try_find_frame_with_selector(
                "input[name='#ICOrigFileName']",
                state="attached",
                timeout=5_000,
            ) is not None or self._find_attachment_file_input_on_page(
                timeout=250,
            ) is not None:
                return

        raise RuntimeError(
            "Add Attachment button was found but File Attachment dialog did not open."
        )

    def _find_attachment_file_input_on_page(
        self,
        timeout: int = 1_000,
    ) -> Locator | None:
        """
        Return the PeopleSoft attachment file input when it is on the page.
        """
        deadline = monotonic() + timeout / 1000

        while monotonic() < deadline:
            for selector in [
                "input[name='#ICOrigFileName']",
                "input[id='#ICOrigFileName']",
                "input[name*='ICOrigFileName']",
                "input[id*='ICOrigFileName']",
                "input[type='file']",
            ]:
                locator = self.page.locator(selector).first

                if self._is_attached(locator):
                    return locator

            sleep(0.1)

        return None

    def _set_attachment_file_input(
        self,
        file_input: Locator,
        txt_file_path: Path,
        frame: Frame | None = None,
    ) -> None:
        """
        Set the PeopleSoft attachment file and ensure the Upload button is enabled.
        """
        file_input.wait_for(state="attached", timeout=10_000)
        file_input.set_input_files(str(txt_file_path.resolve()))

        scope = frame if frame is not None else self.page
        try:
            scope.evaluate(
                """
                () => {
                  const input = document.querySelector('input[name="#ICOrigFileName"], input[type="file"]');
                  if (input) {
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                  }
                  if (typeof window.enableUpload === "function") {
                    window.enableUpload();
                  }
                  const upload = document.querySelector('#Upload, input[name="Upload"]');
                  if (upload) {
                    upload.disabled = false;
                    upload.removeAttribute("disabled");
                  }
                }
                """
            )
        except Exception:
            logger.info("PeopleSoft attachment enable script was not available.")

    def _click_upload(self) -> None:
        """
        Click Upload button.
        """
        if self._is_add_attachment_success_visible() or self._is_any_visible(
            [
                "#upload_ok_button",
                *RUN_BUTTON_SELECTORS,
                "input[name='#ICSave']",
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

        upload_button = self._find_first_visible_locator(
            [
                "#upload_button",
                "#Upload",
                "[name='Upload']",
                "input[id='Upload']",
                "input[name='Upload']",
                "input[value='Upload']",
                "input[title='Upload']",
                "button:text-is('Upload')",
                "a:text-is('Upload')",
            ],
            timeout=20_000,
        )
        self._click_upload_button(upload_button)

    def _click_upload_button(
        self,
        upload_button: Locator,
    ) -> None:
        """
        Click Upload in the File Attachment dialog.
        """
        click_attempts = [
            lambda: self._click_visible_locator(upload_button),
            lambda: upload_button.click(force=True, timeout=5_000),
            lambda: self._click_visible_locator_by_mouse(upload_button),
        ]

        for click_attempt in click_attempts:
            try:
                click_attempt()
                return
            except Exception:
                continue

        raise RuntimeError("Upload button was found but could not be clicked.")

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
            ok_button = self._find_message_ok_locator(timeout=10_000)
            self._click_upload_message_ok(ok_button)
        except Exception:
            if self._click_message_ok_with_script(timeout_seconds=10):
                if not self._try_wait_after_message_ok(timeout=10_000):
                    raise
            elif not self._click_add_attachment_ok_with_script():
                raise
            else:
                if not self._try_wait_after_message_ok(timeout=10_000):
                    raise

        if not self._try_wait_after_message_ok(timeout=30_000):
            raise RuntimeError(
                "Upload Message OK was clicked, but Run button did not appear."
            )
        self._upload_ok_confirmed = True
        if self._is_any_visible(["input[name='#ICSave']"]):
            self._run_requested = True

    def _click_upload_message_ok(
        self,
        ok_button: Locator,
    ) -> None:
        """
        Click upload Message OK using multiple PeopleSoft-safe methods.
        """
        click_attempts = [
            lambda: self._click_visible_locator(ok_button),
            lambda: ok_button.click(force=True, timeout=5_000),
            lambda: self._click_visible_locator_by_mouse(ok_button),
        ]

        for click_attempt in click_attempts:
            try:
                click_attempt()
            except Exception:
                continue

            if self._try_wait_after_message_ok(timeout=5_000):
                return

        if self._click_message_ok_with_script(timeout_seconds=5):
            if self._try_wait_after_message_ok(timeout=5_000):
                return

        raise RuntimeError("PeopleSoft Message OK was found but did not close.")

    def _wait_after_message_ok(self) -> None:
        """
        Wait until the upload message OK leads to Run or Process Scheduler.
        """
        self._wait_for_any_visible(
            [
                *RUN_BUTTON_SELECTORS,
                "input[name='#ICSave']",
            ],
            timeout=30_000,
        )

    def _try_wait_after_message_ok(
        self,
        timeout: int = 10_000,
    ) -> bool:
        """
        Return True when upload Message OK leads to Run or Process Scheduler.
        """
        try:
            self._wait_for_any_visible(
                [
                    *RUN_BUTTON_SELECTORS,
                    "input[name='#ICSave']",
                ],
                timeout=timeout,
            )
            return True
        except Exception:
            return False

    def _find_message_ok_locator(
        self,
        timeout: int = 10_000,
    ) -> Locator:
        """
        Find the OK button from the upload Message popup.
        """
        try:
            return self._find_first_visible_locator(
                [
                    "input[name='#ICOK']",
                    "input[id='#ICOK']",
                    "input[name*='ICOK']",
                    "input[id*='ICOK']",
                    "input[title='OK']",
                    "input[title*='OK']",
                    "input[value='OK']",
                    "input[value=' OK ']",
                    "input[value*='OK']",
                    "button:has-text('OK')",
                    "a:has-text('OK')",
                    "#upload_ok_button",
                ],
                timeout=timeout,
            )
        except Exception:
            return self._find_first_visible_locator(
                [
                    "[role='dialog'] input[value='OK']",
                    "[role='dialog'] input[value*='OK']",
                    "[role='dialog'] button:has-text('OK')",
                    ".PSMODAL input[value='OK']",
                    ".PSMODAL input[value*='OK']",
                    ".PSMODAL button:has-text('OK')",
                    ".ps_box-modal input[value='OK']",
                    ".ps_box-modal input[value*='OK']",
                    ".ps_box-modal button:has-text('OK')",
                ],
                timeout=timeout,
            )

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

        if self._is_any_visible(["input[name='#ICSave']", "#run_ok_button"]):
            self._run_requested = True
            return

        run_button = self._find_first_visible_locator(
            RUN_BUTTON_SELECTORS,
            timeout=20_000,
        )
        self._click_run_button(run_button)
        self._run_requested = True
        self._wait_for_any_visible(
            [
                "input[name='#ICSave']",
                "#run_ok_button",
            ],
            timeout=30_000,
        )

    def _click_run_button(
        self,
        run_button: Locator,
    ) -> None:
        """
        Click Run with fallbacks for PeopleSoft button rendering.
        """
        click_attempts = [
            lambda: self._click_visible_locator(run_button),
            lambda: run_button.click(force=True, timeout=5_000),
            lambda: self._click_visible_locator_by_mouse(run_button),
            lambda: self._click_run_with_script(timeout_seconds=5),
        ]

        for click_attempt in click_attempts:
            try:
                click_attempt()
            except Exception:
                continue

            if self._is_any_visible(["input[name='#ICSave']", "#run_ok_button"]):
                return

            try:
                self._wait_for_any_visible(
                    [
                        "input[name='#ICSave']",
                        "#run_ok_button",
                    ],
                    timeout=5_000,
                )
                return
            except Exception:
                continue

        raise RuntimeError("Run button was found but Process Scheduler did not open.")

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

    def _is_upload_message_visible(self) -> bool:
        """
        Return True when the AddAttachment Message OK is currently visible.
        """
        if self._is_any_visible(
            [
                "input[name='#ICOK']",
                "input[id='#ICOK']",
                "input[name*='ICOK']",
                "input[id*='ICOK']",
                "input[value='OK']",
                "button:has-text('OK')",
                "#upload_ok_button",
            ]
        ):
            return True

        for scope in self._locator_scopes():
            try:
                page_text = str(
                    scope.evaluate(
                        "() => document.body ? document.body.innerText : ''"
                    )
                )
            except Exception:
                continue

            if "AddAttachment" in page_text and "succeeded" in page_text:
                return True

        return False

    def _is_add_attachment_success_visible(self) -> bool:
        """
        Return True only when PeopleSoft shows the AddAttachment success message.
        """
        for scope in self._locator_scopes():
            try:
                page_text = str(
                    scope.evaluate(
                        "() => document.body ? document.body.innerText : ''"
                    )
                )
            except Exception:
                continue

            if "AddAttachment" in page_text and "succeeded" in page_text:
                return True

        return False

    def _is_filename_populated(self) -> bool:
        """
        Return True when HRIS already shows an uploaded filename.
        """
        for scope in self._locator_scopes():
            try:
                if bool(scope.evaluate(FILENAME_POPULATED_SCRIPT)):
                    return True
            except Exception:
                continue

        return False

    def _click_message_ok_with_script(
        self,
        timeout_seconds: int = 10,
    ) -> bool:
        """
        Click a visible PeopleSoft Message OK with a broad DOM fallback.
        """
        deadline = monotonic() + timeout_seconds

        while monotonic() < deadline:
            for scope in self._locator_scopes():
                try:
                    clicked = bool(scope.evaluate(MESSAGE_OK_CLICK_SCRIPT))
                except Exception:
                    continue

                if clicked:
                    return True

            sleep(0.25)

        return False

    def _click_run_with_script(
        self,
        timeout_seconds: int = 10,
    ) -> bool:
        """
        Click a visible PeopleSoft Run button with a DOM fallback.
        """
        deadline = monotonic() + timeout_seconds

        while monotonic() < deadline:
            for scope in self._locator_scopes():
                try:
                    clicked = bool(scope.evaluate(RUN_CLICK_SCRIPT))
                except Exception:
                    continue

                if clicked:
                    return True

            sleep(0.25)

        return False

    def _click_add_attachment_with_script(
        self,
        timeout_seconds: int = 10,
    ) -> bool:
        """
        Click a visible PeopleSoft Add Attachment button with a DOM fallback.
        """
        deadline = monotonic() + timeout_seconds

        while monotonic() < deadline:
            for scope in self._locator_scopes():
                try:
                    clicked = bool(scope.evaluate(ADD_ATTACHMENT_CLICK_SCRIPT))
                except Exception:
                    continue

                if clicked:
                    return True

            sleep(0.25)

        return False

    @staticmethod
    def _assert_field_value(
        locator: Locator,
        expected_value: str,
        field_name: str,
    ) -> None:
        """
        Ensure Playwright did not move on before a date field accepted input.
        """
        actual_value = locator.input_value(timeout=5_000).strip()

        if actual_value != expected_value:
            raise RuntimeError(
                f"{field_name} was not filled correctly. "
                f"Expected={expected_value}, Actual={actual_value}"
            )

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
                "#start_date",
                "#end_date",
                "#attachment_file",
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
        return [self.page, *getattr(self.page, "frames", [])]

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

    def _click_visible_locator_by_mouse(
        self,
        locator: Locator,
    ) -> None:
        """
        Click the visible center point without letting Playwright auto-scroll.
        """
        locator.wait_for(
            state="visible",
            timeout=10_000,
        )

        box = locator.bounding_box(timeout=5_000)

        if box is None:
            locator.click(force=True)
            return

        self.page.mouse.click(
            box["x"] + box["width"] / 2,
            box["y"] + box["height"] / 2,
        )
