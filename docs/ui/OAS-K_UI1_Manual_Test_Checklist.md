# OAS-K UI1 Manual Test Checklist

Use the source-only manual launcher:

```powershell
py tools/ui_test/run_unified_ui.py
```

Do not run a packaging command. Before testing, confirm that no engine job is
active.

## Window and layout

- [ ] One window opens with title `Office Automation Suite – Karina`.
- [ ] Window icon appears when supported by Windows/Tk.
- [ ] Default size is approximately 1180×720 and the window is centered.
- [ ] Window is resizable and does not shrink below 1000×640.
- [ ] Sidebar, header, content area, and status bar remain aligned after resize.
- [ ] Theme is light, compact, readable, and has no gradient/background image.

## Navigation

- [ ] Dashboard is active at startup.
- [ ] Sidebar has exactly eight menus in the documented order.
- [ ] Attendance opens in the same content area.
- [ ] Outlook Revisi opens in the same content area.
- [ ] HRIS opens in the same content area.
- [ ] Utilities opens and shows Comparison Result plus Attachment Consolidation.
- [ ] History opens and displays an empty-state table.
- [ ] Settings opens with descriptive inactive sections.
- [ ] System Health opens with static “Belum diperiksa” categories.
- [ ] Active marker and bold text move to the selected menu.
- [ ] Header title and subtitle follow the selected menu.
- [ ] Status bar follows the selected menu.
- [ ] Tab focus reaches sidebar menu buttons and a focused button remains visible.
- [ ] No additional module/top-level window opens.

## Fallback and lifecycle

- [ ] If a sidebar `.ico` is unsupported, its complete text label remains.
- [ ] Missing/corrupt icon warnings do not close the application.
- [ ] Closing the window exits normally without `os._exit`.

## Safety verification

- [ ] No Attendance, Outlook Revisi, HRIS, or Utilities engine starts.
- [ ] No workbook is read.
- [ ] No project or production `.db` file is created.
- [ ] No Data Root folder is created.
- [ ] No production Registry value is written.
- [ ] No JSON window-state or storage-pointer file is created.
- [ ] No backup, restore, import, reset, or configuration import runs.

## Automated runtime evidence

The UI1 Tk smoke suite programmatically confirmed:

- root construction and normal destruction;
- Dashboard-only initial page cache;
- navigation through all eight page IDs;
- one root content area with no module `Toplevel`;
- title, minimum dimensions, resizable state, and page disposal.

Visual appearance, Windows DPI behavior, and human keyboard usability remain
manual release checks because automated structural tests cannot judge them.
