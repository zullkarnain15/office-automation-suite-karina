# OAS-K UI3 Visual Manual Checklist

Date: 2026-07-21
Launcher: `py tools/ui_test/run_unified_ui.py`

- [x] Sidebar displays PNG companion icons for all eight pages.
- [x] Icons are clear in isolated 100% preview.
- [x] Icons and layout remain usable in isolated 125% preview.
- [x] Icons and layout remain usable at actual 150% (`144 DPI`).
- [x] Active marker, soft background, hover, and keyboard focus are clear.
- [x] Spacing, borders, colors, and typography are consistent.
- [x] Dashboard summary/module cards and empty state are readable.
- [x] Dashboard recent output action remains inside the card at minimum height.
- [x] History filters are aligned and the table resizes with a scrollbar.
- [x] History pagination and action row remain visible at minimum height.
- [x] Job detail is available by button/double-click when a row exists.
- [x] System Health cards are consistent and vertically scrollable.
- [x] `Run Checks` completes while the window remains responsive.
- [x] Settings UI2 remains available and its Tk smoke test passes.
- [x] Status bar remains visible at the constrained 1000×640 baseline.
- [x] No operational engine starts.
- [x] Opening the app creates no database/folder.
- [x] Opening the app writes no Registry value.

Evidence screenshots were stored only under the user temporary directory and
were not added to the repository. The 100% and 125% previews used Fake Registry
and a non-created temporary Data Root. The actual 150% run used the normal
source launcher; it performed read-only resolution and no production write.
