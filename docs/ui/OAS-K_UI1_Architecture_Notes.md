# OAS-K UI1 Architecture Notes

Status: COMPLETED
Sprint: UI1 — Unified UI Shell & Navigation
Toolkit: Python standard-library Tkinter/ttk
Engine integration: Not implemented
Database/Registry writes: None

## 1. Purpose and boundary

UI1 provides a lightweight, single-window shell for Office Automation Suite –
Karina. It establishes navigation, page lifecycle, lazy page creation, visual
styles, icons, in-memory window state, error containment, and Indonesian
placeholder content.

UI1 does not invoke engines, configuration readers, database/recovery
operations, Registry services, workbook readers, or output generation. The
legacy launcher and legacy GUI remain unchanged.

## 2. Window layout

`OASKUnifiedApp` builds one resizable `tk.Tk` root:

```text
┌──────────────┬─────────────────────────────────────────────┐
│              │ Header: title, subtitle, application status│
│ Sidebar      ├─────────────────────────────────────────────┤
│ 8 menus      │                                             │
│              │ One shared content area                     │
│              │                                             │
│ Version      ├─────────────────────────────────────────────┤
│              │ Status, selected page, DB placeholder, ver. │
└──────────────┴─────────────────────────────────────────────┘
```

The default geometry is 1180×720, the minimum is 1000×640, and the window is
centered when instantiated. Grid weights make the content area resize while
the sidebar remains compact at 232 pixels.

## 3. Page registry

`PageRegistry` is the only menu metadata source. Duplicate IDs are rejected.
The locked order is:

1. Dashboard
2. Attendance
3. Outlook Revisi
4. HRIS
5. Utilities
6. History
7. Settings
8. System Health

Each `PageDefinition` contains ID, title, subtitle, icon name, and a lazy
factory. The factory imports its page module only on first navigation.

## 4. Lazy loading and cache

Startup creates the root layout, sidebar, header, status bar, and Dashboard.
The other seven page classes are not imported or instantiated until selected.
After creation, a lightweight page is cached and reused.

All pages occupy the same content frame. Navigation never creates a module
`Toplevel`.

## 5. Page lifecycle

`BasePage` defines:

- `on_show()`
- `on_hide()`
- `refresh()`
- `can_navigate_away()`
- `can_close()`
- `dispose()`

Defaults are safe no-ops. Navigation calls the current hide/leave contract,
shows one target, updates header/status/sidebar state, and calls target
`on_show()`. A rejected leave restores the current page. Close checks the
active page and disposes every cached page before destroying the root.

`AppContext` provides only project/assets paths, application version, logger,
an optional lightweight service mapping, and navigation/status callbacks. It
contains no engine.

## 6. Error boundary

Factory exceptions are logged and converted to a safe `ErrorPage`. The error
page does not expose a traceback, the status bar reports the failure, and all
other menus remain usable. Page disposal errors are logged without preventing
the remaining cached pages from disposing.

## 7. Icon behavior

`IconManager` resolves paths with `pathlib`, loads on demand, and retains
`PhotoImage` references in a cache. Missing/corrupt/unsupported files log a
warning and return `None`, so the control remains text-only.

The window icon uses `root.iconbitmap(app.ico)`. Tk 8.6 on the development
machine did not consistently decode the supplied `.ico` files through
`PhotoImage` for widgets; no runtime conversion and no companion PNG were
created. PNG companions may be reviewed in a later visual sprint.

## 8. Style system

`StyleManager` owns the light ttk theme. The main colors are:

- header `#1F4E78`;
- primary action `#2E8B57`;
- background `#F5F5F5`;
- card `#FFFFFF`;
- dark primary text and soft gray borders.

Central styles include `OASK.TFrame`, `Sidebar.TFrame`, `Sidebar.TButton`,
`SidebarActive.TButton`, `Header.TFrame`, `PageTitle.TLabel`,
`PageSubtitle.TLabel`, `ContentCard.TFrame`, `Primary.TButton`,
`Secondary.TButton`, `StatusBar.TFrame`, and `StatusBar.TLabel`.

Sidebar buttons keep keyboard focus. The active item uses bold text, a left
marker, border, and background, so color is not the only indicator.

## 9. Placeholder pages

Dashboard contains module and system-status cards with “Belum diintegrasikan”
or “Belum diperiksa” states. Utilities retains its sidebar name and shows
Comparison Result plus Attachment Consolidation as future subfeatures.

Settings contains descriptive, inactive future sections. History contains an
empty static table structure and performs no query. System Health shows static
categories and performs no check.

## 10. Window state

`WindowState` holds selected page, width, height, and maximized state in memory.
UI1 does not persist it to a file, database, or Registry.

## 11. Test strategy

Headless unit tests cover registry metadata, lazy factory calls, cache,
lifecycle, cancellation, metadata updates, error containment, imports, and
no-persistence boundaries.

Optional Tk smoke tests instantiate and close a real root when a display is
available. They verify the default page, all eight menus, single-root
navigation, resize/minimum size, title, and disposal.

## 12. Technical debt and UI2 recommendation

Deferred items:

- companion PNG navigation icons if visual review approves them;
- high-DPI scaling review on office laptops;
- persisted window preferences after an approved storage contract;
- accessibility review with keyboard-only users and Windows scaling;
- real read-only status adapters;
- module page adapters and long-running task coordination.

UI2 should integrate read-only Dashboard/System Health status first through
small injected interfaces. It should retain lazy imports and must not connect
operational engines until each module has an explicit page adapter, background
task policy, cancellation model, and regression gate.
