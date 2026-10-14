# OAS-K UI8 Theme Architecture

## Scope

UI8 theme foundation lives in `ui/theme/` and is applied from `ui/style_manager.py`.
The change is presentation-only and keeps the existing Page -> Service -> Adapter ->
Engine boundary intact.

## Modules

- `ui/theme/palette.py`: official SNES 16-bit Retro RPG color tokens.
- `ui/theme/typography.py`: bundled font paths, intended families, and fallbacks.
- `ui/theme/font_loader.py`: process-scoped Windows font loading through
  `AddFontResourceExW(..., FR_PRIVATE, ...)`.
- `ui/constants.py`: backward-compatible aliases for existing UI pages.
- `ui/style_manager.py`: central ttk styles for frames, labels, buttons, inputs,
  notebook tabs, treeview, progress, and status labels.
- `ui/icon_manager.py`: PNG companion loading with nearest-neighbor scaling.

## Safety

Font loading does not install fonts, does not write Registry, does not require
administrator rights, and falls back safely when files are missing or unusable.
Theme application does not call any business engine.

## Launcher

`main.py` is now approved as the current source entry point for the unified UI:

```powershell
py main.py
```

The isolated manual launcher remains available for fake Registry/test-data-root
checks:

```powershell
py tools/ui_test/run_unified_ui.py --test-data-root <temporary-path>
```
