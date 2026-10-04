# React control UI migration status

Date: 2026-10-04
Branch: `main`
Repository: `B1progame/ccrosshair`

Recoverable pre-migration checkpoint: `990f991ffcc80180ddbbf47f543ee1e1e487a559`, also published as `backup/pre-react-migration-20261004-183629` on GitHub.

PySide6 remains the desktop host and owns overlay, zoom, global input, tray, settings, game profiles, storage, and update services. The normal control window is now one offline React/Vite shell served from the bundled `crosshair://ui` scheme. Python owns persisted and native state; the versioned WebChannel bridge validates commands and returns correlated results. The classic Qt pages remain available through **Switch to classic controls** as a recovery surface.

## Feature parity matrix

| Area | React surface and native action | Status / evidence |
| --- | --- | --- |
| Home and overlay | Runtime status, active crosshair, quick activation, size controls, overlay toggle | Implemented; Qt-hosted screenshot captured |
| Library | Search, bounded 36-style pages, filters, preview selection, favorites, activation, detail navigation | Implemented; 37 built-ins smoke-captured; catalog query tested at 100, 1,000, and 10,000 items |
| My Crosshairs | Favorites, imported and custom collection filters | Implemented; collection/filter regression tests pass |
| Detail/Edit | Native-matched preview, live color/opacity/geometry edits, save variant, send to creator, export | Implemented; detail page captured; slider updates commit on release |
| Creator | Grid drawing, erase, undo/redo, grid/color/name settings, save/activate, save-only, export | Implemented; page captured; creator IDs now avoid built-in collisions and preserve edits to existing creator designs |
| Games | Native scan status, manual executable import, searchable profile style and enable controls, fullscreen/game switches | Implemented; page captured; native game scanning stays in a worker |
| Zoom/Beta | Visibility gate, zoom/live enablement, hotkey, monitor, scale, placement, animation settings | Implemented; page captured; native capture remains outside WebChannel |
| Export | Import packs, export active or selected styles, paginated selection catalog | Implemented; page captured |
| Settings | Theme/system resolution, contrast-aware accent, sizes, startup, storage picker, update check, reset, quit | Implemented; page captured |
| About and recovery | Version/runtime state, updates, explicit classic-controls fallback | Implemented; page captured |
| Bridge/runtime | Typed TS contracts, payload allowlists, request IDs, errors, revision ordering, reconnect, trusted local scheme | Implemented; Python compilation and Qt-hosted page load pass |

## Verification

- Python: `PYTHONPATH=src python -m unittest discover -s tests -v` — 9 tests passed.
- Python import/bytecode check: `python -m compileall -q src tests` — passed.
- Frontend: `npm --prefix frontend run build` — TypeScript and Vite production build passed. Bundle: 338.39 kB JavaScript (109.62 kB gzip), 19.86 kB CSS (4.51 kB gzip).
- Catalog query microbenchmark (20 runs per size, synthetic definitions, this host): 100 items median 0.032 ms / p95 0.037 ms; 1,000 items 0.281 / 0.299 ms; 10,000 items 2.947 / 3.802 ms. This measures the bounded Python query path, not end-to-end browser scroll latency.
- Qt-hosted WebEngine smoke capture loaded all nine regular pages and the Detail page. Screenshots were captured at 980×600, 1280×800, and 1440×900, including collapsed navigation. The VM required `--disable-gpu`; Chromium reports unavailable virtualized GLES contexts, then page rendering succeeds. Current captures are in `artifacts/ui-audit/`.
- PyInstaller `--onedir --windowed` completed and included the current offline `webui/dist` assets at `_internal/crosshair_overlay/webui/dist/`. The portable directory is 620,074,894 bytes (about 591 MiB). A complete interactive smoke test of the packaged executable, installer build, and installer size were not verified here.

## Visual evidence

- Before: `artifacts/ui-audit/main-window-web.png` (partial React library surface).
- After: `artifacts/ui-audit/react-home.png`, `react-library.png`, `react-my-crosshairs.png`, `react-detail.png`, `react-creator.png`, `react-games.png`, `react-zoom.png`, `react-export.png`, `react-settings.png`, and `react-about.png`. Responsive captures: `responsive-980-library.png`, `responsive-980-creator.png`, `collapsed-980-creator.png`, and `large-1440-home.png`.
- Native-matched preview check: `artifacts/ui-audit/native-matched-preview.png`.

These are actual Qt-hosted captures at 1280x800. The after captures were visually inspected for the library, detail editor, and creator. No numeric before/after startup, idle CPU, hidden CPU, or WebEngine memory baseline was available, so no performance improvement is claimed for those measures. Bridge reload/disconnect, creator file round trips, import/export cancellation, fullscreen detection, tray hide/show, and overlay responsiveness during UI suspension still need dedicated end-to-end checks.
