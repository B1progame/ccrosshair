# Changelog

## 1.5.3 - 2026-10-06

- Redesigned the Games page with clearer runtime status, profile counts, grouped automation and shortcuts, and focused per-game cards with expandable loadout tuning.
- Verified Quality mode performs local ONNX 3× super-resolution inference; on the release host DirectML produced a 672×672 result in 27.5 ms for the test frame. CPU fallback is available where DirectML is unavailable.

## 1.5.2 - 2026-10-06

- Fixed the Zoom and Compatibility pages crashing to a blank screen before any live diagnostics exist; missing diagnostics now use safe defaults.
- Made the updater show Inno Setup's install progress bar after the download, record update/setup logs, and relaunch the existing app if installation fails.

## 1.5.1 - 2026-10-05

- Fixed the blank control window by queuing the first Qt WebEngine load until after the native window is shown, avoiding a Windows WebEngine crash during the window's show event.

## 1.5.0 - 2026-10-05

- Fixed the blank native control window on Windows systems where QtWebEngine loses its D3D compositor context; the lightweight React UI now uses reliable software rendering.
- Fixed creator strokes stopping when WebEngine rejects pointer capture; drawing now continues without capture and interpolates fast drags across skipped cells.
- Clarified that local 3× AI upscaling runs in Zoom's Quality mode, while center-mask reticle cleanup is approximate preview-only processing and cannot change the game's built-in crosshair.
- Added hold/toggle Zoom hotkey activation while preserving hold behavior by default.
- Added configurable press-only or held-fire repeat cadence globally and per game loadout.
- Added a privacy-safe grouped settings-backup preview and guarded restore flow; current settings remain recoverable and restart applies the restored file.
- Added a guided per-display desktop-capture probe and source-linked game crosshair guidance without changing game settings.
- Made Zoom and its local AI upscaler discoverable without enabling a separate beta preference; the page now shows the actual model/provider diagnostics and Quality mode.

### Known limits
- AI super-resolution enhances the Zoom preview only. It cannot remove the game's reticle from the game itself. Preview cleanup remains an approximate center-mask fill, not AI inpainting.
- Real game capture compatibility and gameplay performance remain unverified; see `FEATURE_STATUS.md` for measured results and outstanding checks.

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
