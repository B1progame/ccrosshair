# Changelog

## 1.2.2 - 2026-10-05

### Improvements
- Replaced the classic Qt control pages with the React control interface.
- Made creator-canvas drawing and drag-to-paint more reliable with pointer capture.
- Reduced crosshair overlay flashes caused by brief fullscreen detection and game process scan gaps.
- Avoided screen captures when Zoom is inactive.

### Bug Fixes
- Fixed backend creator save behavior, worker cleanup, and startup update preference handling.
- Removed the legacy native-page fallback so the React interface is the only control surface.

## 1.2.0 - 2026-04-21

### UI Changes
- Set the default accent color to `#A923E2`.
- Reworked the Home overlay control into one stateful button:
  - `Deactivate` in gray while overlay is active.
  - `Activate` in accent color while overlay is inactive.
- Improved Crosshairs page structure with cleaner row layout for controls and content.
- Improved rounded corner rendering for preview surfaces and scroll sections.

### Bug Fixes
- Fixed UI text clipping and overflow issues in Crosshairs and Detail views by adding scroll-safe layouts.
- Fixed folder/button restyling refresh issues when switching filters.
- Fixed favorite heart symbol rendering issues by using stable unicode escape sequences.

