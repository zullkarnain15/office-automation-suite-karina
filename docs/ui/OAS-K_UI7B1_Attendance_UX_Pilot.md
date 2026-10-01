# OAS-K UI7B.1 Attendance Operational UX Pilot

## Purpose

UI7B.1 is a presentation-only pilot for a simpler desktop operational workflow. It reduces navigation width and replaces the previous Attendance card grid without changing the Page → Service → Adapter → Engine boundary, SQLite configuration, job lifecycle, or business rules.

The pilot applies only to Attendance. Outlook Revisi, HRIS, and Utilities retain their existing page implementations until the user evaluates this pilot.

## Before and after

| Area | Previous Unified UI | UI7B.1 pilot |
|---|---|---|
| Sidebar | 232 px, 10–11 pt visual weight, 22 px icons, tall items, brand subtitle | 170 px, 9 pt items, 18 px icons, 34–38 px items, compact OAS-K brand |
| Configuration | Large card with three actions | Two-line summary strip with Detail and Settings |
| Operation inputs | Separate configuration/output/period cards | One horizontal Periode / Workflow / Output panel |
| Validation/run | Large card and vertically stacked full-width buttons | Compact status left; Validate/Run/Cancel aligned right |
| Progress | Separate expanding panel | Always-present stage label and progress bar on one line |
| Log | Large idle card | Five-line dark log, scrollbar, copy/open, and true expand mode |
| Result | Large empty card before processing | Hidden until a result exists, then compact one-line summary |
| Fallback | Mixed into normal workflow | Collapsed Advanced section, session-only |

## Visual hierarchy

The shell header remains the page header and already displays the Attendance title, subtitle, and application status. The Attendance content uses one clear sequence:

1. compact SQLite configuration summary;
2. primary operational panel;
3. validation and action row;
4. compact progress;
5. process log;
6. result only after execution;
7. collapsed Advanced/manual fallback.

The page no longer imports or uses `ResponsiveCardGrid` or `ModernCard`. Thin neutral borders, restrained typography, compact buttons, and a single green primary action replace equally weighted large cards.

## Normal workflow

The normal flow exposes:

- calendar-backed Start and End dates in `MM/DD/YYYY`;
- `Gunakan periode dari Settings`, with read-only fields when selected;
- horizontal Head Office/Branch choice;
- compact HRIS TXT and Excel Report options;
- read-only global output summary;
- Periksa Data and Jalankan Attendance on one action row;
- Batal only while a job is active.

There is no main-flow Browse Configuration or Browse Output. Active configuration reloads automatically whenever the cached page is shown again, including after returning from Settings.

## Advanced workflow

Advanced is closed by default and contains only per-job controls:

- temporary Attendance workbook;
- alternate output folder.

Manual dates remain visible in the main operational panel, as agreed during design discussion. Selecting a temporary workbook or output never updates SQLite. Opening Advanced reduces idle log height; expanding the log temporarily hides progress and Advanced so the operator receives useful log space at the minimum window/DPI combinations.

## Responsive behavior

- At 1180×720, Periode, Workflow, and Output remain in one row with full labels.
- At 1000×640, the same controls use a compact one-row allocation that preserves visible Run and usable idle log space.
- Below the supported minimum, the operational panel can reflow Periode above Workflow/Output.
- High-DPI compact mode shortens only the HO control label; fonts are never dynamically reduced.
- Process-log content owns its scrollbar. Result detail and Advanced remain secondary to the normal workflow.

Measured minimum-window checks kept Run visible at simulated 100%, 125%, and 150% Tk scaling. At 150%, idle log space intentionally prioritizes controls; Perbesar Log reallocates progress/Advanced space to the log.

## Preserved behavior

UI7B.1 retains SQLite normal configuration, workbook fallback, HO/Branch, global/manual period and output, TXT/report selection, read-only validation, confirmation, TaskRunner execution, typed progress/log events, cooperative cancellation, navigation guard, job history/status/file references, output naming, and legacy GUI availability.

No Attendance engine/service/adapter contract, SQLite schema, output format, import/export, `main.py`, or other operational page was changed.

## Feedback gate

This pilot must be evaluated by the user before its visual pattern is propagated. In particular, confirm the 170 px sidebar, compact configuration strip, one-row operating panel, log behavior, and Advanced placement. Outlook/HRIS/Utilities redesign belongs to a later explicitly authorized sprint.
