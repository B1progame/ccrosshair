# Changelog

## 1.4.0 - 2026-10-05

### Crosshair Library
- Added 210 original, locally authored pixel designs: 150 practical patterns and 60 novelty/joke crosshairs.
- Added a provenance-rich offline manifest and wired every design through catalog search, preview, serialization, and native overlay drawing.
- Preserved all 100 v1.2.3 catalog entries.

### Creator and Zoom Fixes
- Changed creator saves to return the actual saved style ID and surface filesystem failures so a failed write cannot look successful.
- Set `N` as the default Zoom hotkey and migrate the former shipped `Ctrl+Alt+Z` default to `N`; text entry in the control app suppresses the hotkey.
- Added a Zoom setting to hide the crosshair while the magnifier is visible and restore it afterward.
- Fixed the Qt transform enum used by the Zoom worker, which previously prevented processed frames from being delivered.
- Kept local checksum-verified 3× AI upscaling in the Quality mode, with DirectML/CPU selection and smooth-scaling fallback.
- Fixed the blank control window: register a valid default port and CORS/fetch permissions for the app-local URL scheme, and explicitly allow that scheme in the React bundle's content security policy.

### Verification
- 66 Python unit tests passed, including actual custom-grid rendering/round-trip checks for all 210 new designs, a WebEngine React-mount regression, and local AI inference.
- Frontend TypeScript and production bundle build passed.
- Windows executable and installer build/launch checks are part of the release validation.

## 1.2.3 - 2026-10-05

### Bug Fixes
- Pinned frozen-app Qt DLL and plugin lookup to the bundled PySide6 runtime to prevent import failures when another Qt installation is present.
- Applied the supplied crosshair artwork to the app window, taskbar, and Windows installer icons.
- Moved zoom-frame scaling off the GUI thread and discard queued frames after a zoom session ends.
- Added keyboard zoom steps, reset, common zoom presets, and live frame/drop diagnostics.
- Improved settings migration and preserve valid settings backups during corruption recovery.

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
