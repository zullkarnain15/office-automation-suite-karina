# OAS-K UI8 Manual Checklist

Normal feature/module testing:

```powershell
py main.py
```

Use a temporary test data root for isolated storage testing:

```powershell
py tools/ui_test/run_unified_ui.py --test-data-root <temporary-path>
```

## Theme

- Retro RPG theme is visible but still professional.
- Silkscreen body text is readable and not oversized.
- Buttons are compact and do not crowd the layout.
- Primary, secondary, danger, and tertiary actions are visually distinct.
- Danger actions stay red.
- No blur, glow, gradient, animation, or heavy shadow is visible.

## Sidebar

- Sidebar width stays 230 px.
- Menu labels remain readable, including Outlook Revisi and System Health.
- Active state is clear.
- Icons look crisp at 18 px.

## Attendance

- Compact UI7B.1 layout remains.
- Run button is visible at 1180x720 and 1000x640.
- Validate and Run stay on the same action row.
- Result remains hidden before run.
- Advanced fallback remains closed by default.

## Safety

- Opening pages does not run engines.
- No Registry write occurs from theme loading.
- No production database or Data Root is created from page open.
- HRIS upload remains manual.
- Outlook email is not sent automatically.
- `main.py` opens the unified UI.
