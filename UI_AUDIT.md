# UI Audit - CC Crosshair

## Scope
- Date: 2026-04-21
- Entry shell: `src/crosshair_overlay/ui/`
- Main controller integration: `src/crosshair_overlay/app.py`

## UI Map

### Main Window Shell
- File: `src/crosshair_overlay/ui/main_window.py`
- Purpose: application shell, page router, sidebar collapse behavior, signal bridge to controller.
- Elements:
  - animated sidebar width
  - stacked pages
  - content surface container
- User flow:
  - user clicks sidebar item
  - window routes to page
  - page emits actions to app controller
- Issues:
  - no dedicated Export/About pages
  - navigation labels do not fully match product mental model
  - page transitions are instant, no content transition animation
- Improvements:
  - add Export/About pages
  - add fade transition for page switch
  - map sidebar to explicit task domains

### Sidebar
- File: `src/crosshair_overlay/ui/sidebar.py`
- Purpose: primary navigation and collapse control.
- Elements:
  - nav buttons
  - brand card
  - chevron collapse control
- User flow:
  - toggle collapse, navigate to pages
- Issues:
  - information architecture is feature-based but not workflow-based
  - missing About and Export entries
  - no theme quick switch in nav context
- Improvements:
  - restructure sections: Library, My Crosshairs, Export, Settings, About
  - keep collapse animation
  - add quick theme cycle affordance

### Home Page
- File: `src/crosshair_overlay/ui/pages/home_page.py`
- Purpose: dashboard and quick runtime control.
- Elements:
  - status chip
  - crosshair preview
  - quick style selector
  - overlay toggle action
- Issues:
  - previously dual state controls were confusing (already improved)
  - page switch feel could be smoother
- Improvements:
  - keep single toggle model
  - stronger visual hierarchy and transitions

### Crosshairs Library Page
- File: `src/crosshair_overlay/ui/pages/crosshairs_page.py`
- Purpose: browse, preview, select, favorite, import/export packs.
- Elements:
  - search
  - folder/filter row
  - crosshair card grid
  - selection and actions cards
- Issues:
  - large lists can feel heavy due to synchronous full redraw
  - no dedicated “My Crosshairs” quick mode in navigation
  - random/discovery UX not explicit
- Improvements:
  - add batched tile population for smoother rendering
  - add quick view API for nav mode switching
  - support reusable card widget pattern

### Crosshair Detail Page
- File: `src/crosshair_overlay/ui/pages/crosshair_detail_page.py`
- Purpose: edit supported style parameters, live preview, save/export/send to editor.
- Elements:
  - dynamic form
  - dual preview surfaces
  - action row
- Issues:
  - complex content can clip on smaller windows (partially addressed)
- Improvements:
  - keep scroll-safe layout
  - align control spacing and labels with global tokens

### Creator Page
- File: `src/crosshair_overlay/ui/pages/creator_page.py`
- Purpose: draw/edit grid-based crosshair and save/export.
- Elements:
  - tools, canvas, previews, action buttons
- Issues:
  - dense controls and many equal-weight actions
- Improvements:
  - maintain functionality but move toward componentized controls
  - unify button and card visuals with tokenized style system

### Games Page
- File: `src/crosshair_overlay/ui/pages/games_page.py`
- Purpose: runtime game profile mapping and automation toggles.
- Elements:
  - auto toggle checkboxes
  - scan/import actions
  - per-game row + modal
- Issues:
  - modal flow is clear but visually static
- Improvements:
  - keep modal but modernize row interactions and hover feedback

### Settings Page
- File: `src/crosshair_overlay/ui/pages/settings_page.py`
- Purpose: theme, accent, storage, beta visibility, maintenance actions.
- Elements:
  - theme slider
  - accent color picker
  - global size
  - storage chooser
- Issues:
  - no quick theme action from navigation context
- Improvements:
  - preserve full controls
  - add sidebar quick theme cycle

### Beta Zoom Page
- File: `src/crosshair_overlay/ui/pages/beta_page.py`
- Purpose: zoom mode controls and live preview.
- Elements:
  - mode chooser
  - hotkey and monitor target controls
  - placement and animation controls
- Issues:
  - strong feature depth, but less discoverable when hidden by beta toggle
- Improvements:
  - keep gated behavior and improve consistency with shared styling

## Cross-Cutting Issues
- Styling logic is centralized but implemented as one large generated stylesheet string.
- Reusable UI primitives are limited; several page-local controls should become shared widgets.
- Page transitions are immediate; sidebar animation exists but content animation is missing.
- Performance on large crosshair sets can degrade due to synchronous widget creation.

## Refactor Goals
- Introduce shared `core` and `widgets` modules.
- Add global style token file and keep theme-aware rendering.
- Introduce dedicated Export and About pages.
- Add batched/lazy-ish list rendering in Crosshairs page.
- Preserve existing controller signals and behavior to avoid regressions.
