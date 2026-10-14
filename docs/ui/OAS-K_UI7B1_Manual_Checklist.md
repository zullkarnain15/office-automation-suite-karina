# OAS-K UI7B.1 Manual Checklist

Boundary: source launcher, Fake Registry, temporary Data Root, and fixture/test data only.

## Navigation and layout

- [x] Sidebar final width is 170 px and does not auto-expand.
- [x] Brand subtitle was removed; OAS-K brand is 16 pt.
- [x] Menu is 9 pt with 18 px icons and compact vertical padding.
- [x] Outlook Revisi and System Health remain readable at the final width.
- [x] Attendance uses a desktop operational surface, not a scrolling card/form grid.
- [x] Configuration summary is compact and Settings remains available.
- [x] Period, horizontal workflow, and output options are immediately understandable.
- [x] Browse Configuration and Browse Output are absent from normal workflow.
- [x] Validate and Run are horizontal; Run is the sole green primary action.
- [x] Cancel is hidden/disabled outside an active job.
- [x] Result is hidden before a run.
- [x] Advanced is closed by default.

## Window and DPI acceptance

- [x] 1180×720: wide one-row operational layout; Run visible without scrolling.
- [x] 1000×640: compact operational layout; Run visible without scrolling.
- [x] Simulated 100% scaling: Run bottom 372 logical px; idle log approximately 103 px.
- [x] Simulated 125% scaling: Run bottom 425 logical px; expandable log remains usable.
- [x] Simulated 150% scaling: Run bottom 474 logical px; Perbesar Log reallocates space from secondary controls.
- [x] Fonts are not dynamically reduced.
- [x] Visual source-GUI capture was inspected at the minimum window.

## Behavior and safety

- [x] Opening Attendance does not call the engine/preflight/run path.
- [x] Opening Attendance creates no database or output and writes no Registry value.
- [x] SQLite remains the normal configuration source.
- [x] Global/manual period and output still resolve through the existing service.
- [x] Workbook fallback remains session-only.
- [x] Validation detail remains available without permanent long paragraphs.
- [x] Progress is stage-based; no fake percentage was introduced.
- [x] Process log retains monospace text, scrollbar, line cap, auto-scroll, Open, Copy, and expand behavior.
- [x] Background success/failure restores busy/navigation state.
- [x] Cooperative cancellation and audit behavior remain covered.
- [x] Outlook, HRIS, and Utilities page source was not changed by UI7B.1.
- [x] Schema remains 24 tables and `main.py` was not changed by UI7B.1.

## Executed commands

```text
py tools/ui_test/run_unified_ui.py --test-data-root <temporary-path>
Launcher stayed responsive; no Data Root creation; no stderr.

py -m pytest tests/ui/attendance -q
14 passed, 1 optional skip

Targeted Attendance regression
38 passed

py -m pytest tests/ui -q
226 passed, 1 optional skip

py -m pytest tests/database tests/storage tests/recovery tests/ui -q
466 passed

py -m pytest -q
601 passed, 1 optional skip

py -m ruff check ui tests/ui tools/ui_test
All checks passed
```
