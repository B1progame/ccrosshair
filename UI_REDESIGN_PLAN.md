# UI Redesign Plan - CC Crosshair

## Strategy
1. Keep runtime behavior stable.
2. Refactor in slices behind current signal contracts.
3. Upgrade architecture and visuals together.

## Planned Architecture

### New Modules
- `src/crosshair_overlay/core/animation_manager.py`
- `src/crosshair_overlay/widgets/toggle_button.py`
- `src/crosshair_overlay/widgets/sidebar_button.py`
- `src/crosshair_overlay/widgets/crosshair_card.py`
- `src/crosshair_overlay/ui/pages/export_page.py`
- `src/crosshair_overlay/ui/pages/about_page.py`
- `src/crosshair_overlay/assets/styles/global.qss`

### Integration Targets
- Sidebar navigation remap to:
  - Crosshair Library
  - My Crosshairs
  - Export
  - Settings
  - About
- Animated stacked-page transitions.
- Theme quick switch in sidebar.
- Crosshair page batched tile population.

## UX Changes
- Consistent spacing, corner radius, shadows, grouping.
- Single-action toggle patterns where state is binary.
- Dedicated Export page (no hidden export controls).
- Better discoverability via explicit navigation structure.

## Performance Changes
- Batch-create crosshair tiles with timer-based chunking.
- Add card preview cache to reduce repeated paint cost.
- Keep UI thread responsive during large gallery refresh.

## Verification
- Compile-check touched modules.
- Manual smoke paths:
  - navigation
  - toggle states
  - export flow
  - theme switching
  - crosshair selection and detail routing
