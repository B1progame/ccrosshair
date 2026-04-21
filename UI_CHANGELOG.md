# UI Changelog

## 2026-04-21 - Major UI/UX Refactor

### Analysis & Planning
- Added [UI_AUDIT.md](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/UI_AUDIT.md) with component-by-component UI map and issues.
- Added [UI_REDESIGN_PLAN.md](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/UI_REDESIGN_PLAN.md) with phased architecture strategy.

### New Architecture
- Added `core` module:
  - [animation_manager.py](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/src/crosshair_overlay/core/animation_manager.py)
- Added `widgets` module:
  - [toggle_button.py](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/src/crosshair_overlay/widgets/toggle_button.py)
  - [sidebar_button.py](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/src/crosshair_overlay/widgets/sidebar_button.py)
  - [crosshair_card.py](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/src/crosshair_overlay/widgets/crosshair_card.py)

### Styling System
- Added tokenized global stylesheet:
  - [global.qss](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/src/crosshair_overlay/assets/styles/global.qss)
- Updated [theme_manager.py](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/src/crosshair_overlay/theme_manager.py) to load global QSS tokens and merge with dynamic palette styling.

### Navigation & UX
- Refactored sidebar structure in [sidebar.py](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/src/crosshair_overlay/ui/sidebar.py):
  - New sections: Library, Workspace, System
  - Added entries: `My Crosshairs`, `Export`, `About`
  - Added sidebar theme quick-switch button
  - Kept collapsible animated behavior
- Updated [main_window.py](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/src/crosshair_overlay/ui/main_window.py):
  - Added new routes: `my_crosshairs`, `export`, `about`
  - Added fade animation on page navigation
  - Synced active style into Export page preview
  - Added `theme_cycle_requested` signal

### New Pages
- Added dedicated Export workspace:
  - [export_page.py](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/src/crosshair_overlay/ui/pages/export_page.py)
  - Export options panel + live preview + direct export action
- Added About page:
  - [about_page.py](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/src/crosshair_overlay/ui/pages/about_page.py)
  - Version, release link, and changelog reader

### Crosshair Library Performance & Flow
- Refactored [crosshairs_page.py](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/src/crosshair_overlay/ui/pages/crosshairs_page.py):
  - Replaced local tile implementation with shared `CrosshairCardButton`
  - Added batched tile creation using `QTimer` to reduce UI stalls
  - Added quick-view mode API (`all` / `my`)
  - Added `My Crosshairs` semantic filtering path for sidebar route

### Controller Integration
- Updated [app.py](/c:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/src/crosshair_overlay/app.py):
  - Connected sidebar theme quick switch signal
  - Added `cycle_theme_mode()` logic for system/dark/light rotation

### Result
- UI is now more modular, workflow-oriented, animated, and scalable.
- Existing functional behaviors are preserved while adding explicit Export/About routes and faster library rendering behavior.
