"""Standalone HRIS DOM recorder for OAS-K diagnostics.

This tool opens Microsoft Edge with Playwright, lets the user log in manually,
then scans the active HRIS page and frames for safe DOM metadata.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


TOOL_NAME = "OAS-K HRIS Recorder"
OUTPUT_ROOT = Path("diagnostics") / "hris_recorder"
EDGE_FALLBACK_PATHS = (
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
)


DOM_SCAN_SCRIPT = r"""
() => {
  const MAX_TEXT = 500;
  const MAX_OPTIONS = 100;

  function cleanText(value) {
    return (value || "").replace(/\s+/g, " ").trim().slice(0, MAX_TEXT);
  }

  function sanitizeUrl(value) {
    if (!value) {
      return "";
    }
    try {
      const parsed = new URL(value, window.location.href);
      parsed.search = "";
      parsed.hash = "";
      return parsed.toString();
    } catch (error) {
      return "";
    }
  }

  function cssEscape(value) {
    if (!value) {
      return "";
    }
    if (window.CSS && CSS.escape) {
      return CSS.escape(value);
    }
    return String(value).replace(/["\\]/g, "\\$&");
  }

  function quoteAttr(value) {
    return String(value || "").replace(/["\\]/g, "\\$&");
  }

  function visibleText(element) {
    if (!element) {
      return "";
    }
    return cleanText(element.innerText || element.textContent || "");
  }

  function nearestLabelText(element) {
    if (!element) {
      return "";
    }

    if (element.id) {
      const explicitLabel = document.querySelector(`label[for="${cssEscape(element.id)}"]`);
      const explicitText = visibleText(explicitLabel);
      if (explicitText) {
        return explicitText;
      }
    }

    const wrappingLabel = element.closest("label");
    const wrappingText = visibleText(wrappingLabel);
    if (wrappingText) {
      return wrappingText;
    }

    const ariaLabelledBy = element.getAttribute("aria-labelledby");
    if (ariaLabelledBy) {
      const labelText = ariaLabelledBy
        .split(/\s+/)
        .map((id) => visibleText(document.getElementById(id)))
        .filter(Boolean)
        .join(" ");
      if (labelText) {
        return cleanText(labelText);
      }
    }

    const parentText = visibleText(element.closest(".form-group, .form-row, .field, td, tr, div"));
    if (parentText) {
      return parentText;
    }

    return "";
  }

  function candidateLocators(element, roleName) {
    const locators = [];
    const id = element.getAttribute("id");
    const name = element.getAttribute("name");
    const ariaLabel = element.getAttribute("aria-label");
    const text = visibleText(element);

    if (id) {
      locators.push(`#${cssEscape(id)}`);
    }
    if (name) {
      locators.push(`[name="${quoteAttr(name)}"]`);
    }
    if (roleName && (text || ariaLabel)) {
      locators.push(`get_by_role("${roleName}", name="${quoteAttr(text || ariaLabel)}")`);
    }
    if (text) {
      locators.push(`get_by_text("${quoteAttr(text)}")`);
    }

    return locators;
  }

  function inputMetadata(element) {
    const type = (element.getAttribute("type") || "text").toLowerCase();
    return {
      tag: element.tagName.toLowerCase(),
      id: element.getAttribute("id") || "",
      name: element.getAttribute("name") || "",
      type,
      placeholder: element.getAttribute("placeholder") || "",
      aria_label: element.getAttribute("aria-label") || "",
      label_text: nearestLabelText(element),
      candidate_locator: candidateLocators(element, "textbox"),
      value: "REDACTED",
    };
  }

  function buttonMetadata(element) {
    return {
      tag: element.tagName.toLowerCase(),
      id: element.getAttribute("id") || "",
      name: element.getAttribute("name") || "",
      text: visibleText(element),
      aria_label: element.getAttribute("aria-label") || "",
      candidate_locator: candidateLocators(element, "button"),
    };
  }

  function linkMetadata(element) {
    return {
      text: visibleText(element),
      href: sanitizeUrl(element.getAttribute("href") || ""),
      candidate_locator: candidateLocators(element, "link"),
    };
  }

  function selectMetadata(element) {
    const options = Array.from(element.options || [])
      .slice(0, MAX_OPTIONS)
      .map((option) => cleanText(option.textContent || ""))
      .filter(Boolean);

    return {
      id: element.getAttribute("id") || "",
      name: element.getAttribute("name") || "",
      label_text: nearestLabelText(element),
      options,
      candidate_locator: candidateLocators(element, "combobox"),
    };
  }

  function isVisible(element) {
    if (!element) {
      return false;
    }
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.visibility !== "hidden"
      && style.display !== "none"
      && rect.width > 0
      && rect.height > 0;
  }

  function modalMetadata(element) {
    const buttons = Array.from(element.querySelectorAll('button, input[type="button"], input[type="submit"], [role="button"]'))
      .filter(isVisible)
      .map(buttonMetadata);

    return {
      role: element.getAttribute("role") || "",
      text: visibleText(element),
      buttons,
    };
  }

  const inputs = Array.from(document.querySelectorAll("input, textarea"))
    .map(inputMetadata);

  const buttons = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"], input[type="reset"], [role="button"]'))
    .map(buttonMetadata);

  const links = Array.from(document.querySelectorAll("a[href]"))
    .map(linkMetadata);

  const selects = Array.from(document.querySelectorAll("select"))
    .map(selectMetadata);

  const modals = Array.from(document.querySelectorAll('[role="dialog"], [role="alertdialog"], dialog, .modal, .modal-dialog'))
    .filter(isVisible)
    .map(modalMetadata);

  return { inputs, buttons, links, selects, modals };
}
"""


def sanitize_url(url: str) -> str:
    """Remove query string and fragment from a URL."""
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except ValueError:
        return ""


def normalize_url(url: str) -> str:
    """Add a default HTTPS scheme when the user types a bare domain."""
    cleaned_url = url.strip()
    if cleaned_url and "://" not in cleaned_url:
        return f"https://{cleaned_url}"
    return cleaned_url


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def make_output_dir() -> Path:
    output_dir = OUTPUT_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def write_log(log_path: Path, lines: list[str]) -> None:
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def scan_frame(frame, index: int) -> dict:
    frame_result = {
        "index": index,
        "name": frame.name or "",
        "title": "",
        "url": sanitize_url(frame.url),
        "inputs": [],
        "buttons": [],
        "links": [],
        "selects": [],
        "modals": [],
    }

    try:
        frame_result["title"] = frame.title()
    except PlaywrightError as error:
        frame_result["title_error"] = str(error)

    try:
        dom_data = frame.evaluate(DOM_SCAN_SCRIPT)
        frame_result.update(dom_data)
    except PlaywrightError as error:
        frame_result["scan_error"] = str(error)
    except Exception as error:  # Keep one failed frame from stopping the scan.
        frame_result["scan_error"] = f"{type(error).__name__}: {error}"

    return frame_result


def launch_edge_browser(playwright, log_lines: list[str]):
    """Launch Microsoft Edge with the Playwright channel, then fallback to common paths."""
    try:
        return playwright.chromium.launch(
            channel="msedge",
            headless=False,
            timeout=15000,
        )
    except PlaywrightError as error:
        log_lines.append(f"{now_iso()} - Edge channel launch warning: {error}")

    for edge_path in EDGE_FALLBACK_PATHS:
        if edge_path.exists():
            log_lines.append(f"{now_iso()} - Trying Edge fallback path: {edge_path}")
            return playwright.chromium.launch(
                executable_path=str(edge_path),
                headless=False,
                timeout=15000,
            )

    raise RuntimeError("Microsoft Edge tidak ditemukan di channel Playwright atau path standar.")


def build_scan_result(page) -> dict:
    try:
        title = page.title()
    except PlaywrightError:
        title = ""

    return {
        "tool": TOOL_NAME,
        "created_at": now_iso(),
        "safety": {
            "cookies_saved": False,
            "storage_saved": False,
            "password_saved": False,
            "tokens_saved": False,
        },
        "page": {
            "title": title,
            "url": sanitize_url(page.url),
        },
        "frames": [scan_frame(frame, index) for index, frame in enumerate(page.frames)],
    }


def select_active_page(context):
    pages = [page for page in context.pages if not page.is_closed()]
    if not pages:
        raise RuntimeError("Tidak ada halaman browser aktif untuk discan.")
    non_blank_pages = [page for page in pages if page.url and page.url != "about:blank"]
    return non_blank_pages[-1] if non_blank_pages else pages[-1]


def main() -> None:
    output_dir = make_output_dir()
    log_path = output_dir / "recorder_log.txt"
    json_path = output_dir / "hris_dom_scan.json"
    screenshot_path = output_dir / "screenshot.png"
    traceback_path = output_dir / "exception_traceback.txt"
    log_lines = [
        f"{now_iso()} - {TOOL_NAME} started.",
        "Safety: no cookies, storage state, local storage, session storage, tokens, or input values are saved.",
    ]

    browser = None
    try:
        hris_url = normalize_url(input("Masukkan HRIS URL: "))
        if not hris_url:
            raise ValueError("HRIS URL wajib diisi.")

        log_lines.append(f"{now_iso()} - Opening Microsoft Edge.")
        with sync_playwright() as playwright:
            browser = launch_edge_browser(playwright, log_lines)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            try:
                page.goto(hris_url, wait_until="commit", timeout=15000)
            except PlaywrightError as error:
                log_lines.append(f"{now_iso()} - Initial navigation warning: {error}")
                print()
                print("Peringatan: navigasi awal lambat/gagal, tetapi browser tetap dibuka.")
                print("Silakan lanjutkan manual di Microsoft Edge.")

            print()
            print(
                "Silakan login HRIS dan navigasi sampai halaman Overtime Upload Attendance. "
                "Setelah halaman siap, tekan ENTER di terminal."
            )
            input()

            page = select_active_page(context)
            log_lines.append(f"{now_iso()} - Scanning active page: {sanitize_url(page.url)}")
            scan_result = build_scan_result(page)

            page.screenshot(path=screenshot_path, full_page=True)
            log_lines.append(f"{now_iso()} - Screenshot saved: {screenshot_path}")

            json_path.write_text(
                json.dumps(scan_result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log_lines.append(f"{now_iso()} - DOM scan saved: {json_path}")

            context.close()
            browser.close()
            browser = None
            log_lines.append(f"{now_iso()} - Browser closed.")

        print()
        print(f"Selesai. Output tersimpan di: {output_dir}")

    except Exception:
        traceback_text = traceback.format_exc()
        traceback_path.write_text(traceback_text, encoding="utf-8")
        log_lines.append(f"{now_iso()} - ERROR. Traceback saved: {traceback_path}")
        print()
        print(f"Terjadi error. Detail tersimpan di: {traceback_path}")
        print(f"Output folder: {output_dir}")
    finally:
        if browser is not None:
            try:
                browser.close()
                log_lines.append(f"{now_iso()} - Browser closed in cleanup.")
            except Exception as cleanup_error:
                log_lines.append(f"{now_iso()} - Browser cleanup failed: {cleanup_error}")
        write_log(log_path, log_lines)


if __name__ == "__main__":
    main()
