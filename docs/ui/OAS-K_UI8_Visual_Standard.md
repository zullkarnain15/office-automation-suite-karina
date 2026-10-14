# OAS-K UI8 Visual Standard

## Theme Identity

Official theme: OAS-K SNES 16-bit Retro RPG Visual Identity.

The UI should read as warm, crisp, office-ready retro: pixel typography,
1 px outlines, compact controls, no blur, no glow, no gradient, no animation,
and no game-like workflow.

## Palette

- Outline / primary text: `#33664d`
- Royal blue / active navigation: `#4D72B8`
- Forest green / primary action: `#5E9C3A`
- Teal / standard buttons: `#2F8F83`
- Old gold / accent and warning: `#D2A15A`
- Ivory white / panels and controls: `#F7F1DD`
- Soft background: `#EAE7DA`
- Danger red: `#B83A3A`

## Typography

- Brand: Press Start 2P, 12 pt
- Page title: Silkscreen Bold, 15 pt
- Section title: Silkscreen Bold, 10 pt
- Body and fields: Silkscreen Regular, 8-9 pt
- Buttons: Silkscreen Bold, 8 pt
- Logs and technical values: VT323, 12 pt

Fonts fall back to Segoe UI or Consolas if unavailable.

## Buttons

Available central styles:

- `RetroPrimary.TButton`
- `RetroSecondary.TButton`
- `RetroDanger.TButton`
- `RetroTertiary.TButton`

Existing `PrimaryAction`, `SecondaryAction`, `DangerAction`, and compact styles
remain supported. Standard non-Start/non-Run buttons use teal with white text.
Start/Run actions and PNG Start buttons keep their dedicated treatment. Buttons
use compact padding so they stay near 30-34 px height at 100% scaling and do not
dominate the workspace.

## Sidebar

Sidebar is 230 px. Menu font remains compact at 10 pt. Icons are requested
at 20 px and scaled with nearest-neighbor when needed.
