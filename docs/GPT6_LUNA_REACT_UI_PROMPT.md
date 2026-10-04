# Prompt 1 — GPT-6 Luna: React UI migration and complete visual redesign

Work in C:\Users\bslid.BENJI-PC\OneDrive\Dokumente\BENJI\APPS\crosshair\v1. Inspect and redesign this crosshair desktop app, migrating the control UI to React while preserving native runtime behavior. Implement and verify the work; do not stop at a plan. This prompt is independent from prompt 2, which contains new runtime features.

## FIRST: preserve the current project on GitHub before implementation

The user explicitly authorizes creating a recoverable checkpoint and updating GitHub main BEFORE any migration or feature implementation. First perform read-only checks: repository instructions, git status including untracked files, current branch, origin URL, diff, ignored project assets, and remote main after fetch. Expected repository is https://github.com/B1progame/ccrosshair.git and the observed local branch was main; verify both again. Do not reset, clean, discard, stash away, or overwrite current work. Inspect changes for credentials/private data before staging; stage intended source and configuration explicitly rather than blindly adding everything. Preserve existing edits, including modifications made by another active chat.

Commit the current project state, including relevant untracked source/configuration. docs/ is currently ignored: explicitly add the two prompt Markdown files and any important project documentation using narrowly scoped git add -f paths, or a narrow ignore exception. Review ignored source assets/build configuration needed to reproduce the app and include them selectively. Do not commit .venv, caches, generated binaries, private user libraries, secrets, or huge model weights. Git checkpoints do not back up ignored user data: explain what is excluded and create a separate local backup of any user data that the implementation will migrate.

Create a uniquely named backup branch and annotated tag from that exact checkpoint commit (e.g. backup/pre-react-migration-<timestamp> or backup/pre-feature-expansion-<timestamp>), and push those named refs to origin. Update remote main with the checkpoint using a normal fast-forward push. If remote main has diverged, preserve the local checkpoint first, then integrate remote changes without discarding either side, commit any resolved merge, and run baseline checks; never force push or rewrite main. If conflicts need a substantive product decision, ask that specific question instead of guessing. Respect branch protection: create a checkpoint PR if direct updates are blocked, attach it to this chat, and wait for main to include the checkpoint before starting implementation. Do not claim a PR alone satisfies the requested main update.

Verify git ls-remote for remote main, backup branch, and tag; record the full commit IDs and a working GitHub commit link. Report any baseline failures without hiding them. If authentication/network/protection prevents the remote checkpoint, stop implementation and explain the exact blocker. Do not proceed solely on a local commit when the requested GitHub checkpoint is missing.

Only after the remote checkpoint is verified, create a codex/ implementation branch and start work. Future rollback should use the backup ref in a separate checkout or a reviewed revert commit, not destructive reset/force push. Do not merge finished implementation into main without a later explicit request. At the start of each prompt independently, checkpoint its own current baseline; when prompt 2 follows prompt 1, preserve the completed migration too. If implementation branches are unmerged, preserve their work and do not switch away or merge them into main without explaining the branch state and obtaining the necessary decision.

## Required architecture: React control UI, native runtime

Use React + TypeScript + Vite for the control window frontend. Embed the production bundle in PySide6 QWebEngineView. Vite is a development tool: the packaged app must start offline without Node/npm, a Vite server, a browser tab, or an internet connection. Prefer bundled resources or a reviewed custom local scheme; verify asset paths, routing, and deployment rather than assuming file:// behaves identically to a dev server. Use hash routing if that simplifies local bundle navigation. Retain native windows for click-through crosshair rendering and live zoom, Python for capture/inference/input/tray/storage/updates, and native file/color dialogs where useful. Do not make overlays depend on React requestAnimationFrame or the control window being visible.

Use a narrow versioned Qt WebChannel bridge, not a generic execute-Python endpoint and not a permanent network server. Python remains the authoritative runtime/settings/catalog state. Define typed command/result/event contracts, request IDs, validation, structured errors, initial snapshot/ready handshake, ordered state revisions, and bounded/coalesced high-frequency updates. Cover navigation-independent commands for selection, preview, activation, favorites, settings, import/export, creator operations, game profiles, zoom settings, updates, and quit/tray behavior. Expose only the bundled trusted frontend to the bridge; block unexpected navigation/remote content, open external links outside the privileged view, and do not render imported text as executable HTML. Avoid passing arbitrary user-supplied filesystem paths into unrestricted bridge actions.

Do not send captured gameplay frames as JSON/base64 across WebChannel at frame rate. Keep hot-path rendering and AI in Python/native workers; send only configuration and throttled telemetry. For control UI preview images, use bounded on-demand assets and refresh revisions. Creator pointer drawing should remain responsive locally, then synchronize validated document changes in batches; do not make every pointer move await Python. Reuse the existing file formats and renderer semantics, with reference fixtures to detect frontend/native preview differences.

Create frontend/ with a lockfile, reusable components, semantic tokens, and a typed bridge adapter. Provide a browser mock adapter strictly for UI development; show mock mode and ensure production fails visibly on bridge loss rather than silently using fake data. Keep a native UI fallback or migration switch until full feature parity and packaged startup have been verified. Migrate one complete vertical slice (catalog/select/activate) first, verify it end-to-end, then migrate remaining screens. Do not delete old pages before parity. Keep global input/cursor behavior in Windows/Python; use ordinary React cursor styling only for local UI controls.

Measure startup time, installer size, WebEngine memory/process count, idle CPU, hidden-to-tray resource use, control UI latency, and native overlay FPS before/after. Pause frontend visual work when hidden and ensure overlays continue after control-window reload/closure. Chromium overhead is a tradeoff to measure, not a performance improvement to assume. Verify WebEngine resources/helpers/locales are packaged in the Windows installer and test a clean-machine/offline install with no Node runtime.

Official references: https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineWidgets/QWebEngineView.html ; https://doc.qt.io/qtforpython-6/PySide6/QtWebChannel/QWebChannel.html ; https://vite.dev/guide/build.html . Recheck current version compatibility during implementation.

Read relevant installed frontend-design, interface-design, React performance, and GSAP skills via find-skills. Use gsap.context()/framework lifecycle cleanup, keyboard focus management, accessible dialogs, and prefers-reduced-motion. Avoid installing Next.js, Electron, or a second desktop runtime for this assignment.

## Stack and boundaries

This is a Windows Python/PySide6 6.11 application using native Qt widgets, QSS, QPainter, signals, and QPropertyAnimation. Retain Python/PySide6 for the native runtime and migrate the control UI to React/TypeScript/Vite as described below. Preserve overlay rendering, click-through behavior, hotkeys, tray integration, game profiles, creator files, import/export formats, storage, startup behavior, and updates. Preserve existing user edits: `src/crosshair_overlay/windows_runtime.py` was already modified when this analysis started; inspect current git status before touching anything. Do not overwrite unrelated changes or commit without being asked.

## Read and use skills first

Read the actual SKILL.md files, follow applicable guidance, and briefly explain the skills selected:

1. `C:\Users\bslid.BENJI-PC\.agents\skills\find-skills\SKILL.md`: discover relevant skills. Check installed skills first and follow the discovery workflow when searching externally. Verify suitability rather than choosing by popularity alone. Prefer existing installed skills; do not install unnecessary packages.
2. `C:\Users\bslid.BENJI-PC\.codex\skills\ui-ux-pro-max\SKILL.md`: use for hierarchy, spacing, contrast, typography, focus, and interaction feedback. Detect the actual stack. Its design search is at `C:\Users\bslid.BENJI-PC\.codex\skills\ui-ux-pro-max\scripts\search.py`. Search one concern at a time. If recommendations are web/marketing oriented, retry narrowly and use desktop guidance as a labeled fallback. Apply React stack guidance to the new frontend, and keep QSS guidance limited to retained native surfaces.
3. `C:\Users\bslid.BENJI-PC\.codex\skills\desktop-ui-design\SKILL.md`: use for native desktop layouts, Windows conventions, keyboard access, and dialogs.
4. `C:\Users\bslid.BENJI-PC\.agents\skills\gsap-core\SKILL.md`: read the requested motion guidance. Apply easing, interruption, cleanup, and reduced-motion principles using native Qt animations. Use GSAP directly for suitable React UI transitions with scoped cleanup and reduced-motion support. Native overlay animations remain in Python/Qt.
5. Consider installed `redesign-existing-projects`, `interface-design`, and `verification-before-completion` if their actual instructions fit. Choose a small useful set rather than loading every design skill.

## Start with evidence

Read repository instructions, `README.md`, `requirements.txt`, `main.py`, and the relevant source. `UI_AUDIT.md` and `UI_REDESIGN_PLAN.md` are historical: Export/About pages, batched gallery creation, and fade transitions already exist. Verify every old claim against current code.

Map the controller-to-page signal paths in `src/crosshair_overlay/app.py`, then inspect:

- `ui/main_window.py`, `ui/sidebar.py`, and `ui/components.py`
- `theme_manager.py` and `assets/styles/global.qss`
- `widgets/crosshair_card.py`, `widgets/sidebar_button.py`, and `widgets/toggle_button.py`
- `core/animation_manager.py`
- Every page under `ui/pages/`, especially library, detail, creator, home, settings, games, and zoom
- Creator editor and history code where UI interactions depend on them

Launch the real app through the project environment when possible. Inspect every navigation page, both sidebar states, themes, dialogs, search, selection, and minimum window size. The optional `docs/capture_ui_audit.py` renders four pages without starting the overlay/controller or changing persisted settings. Baseline captures are in `docs/ui-audit/`. Those offscreen captures show text as missing-glyph boxes; verify actual Windows rendering before calling that a product bug. They also omit controller-provided runtime data, so an empty Home preview in them is not proof of a runtime bug.

Record reproducible issues with severity, file/function, trigger, observed behavior, and expected behavior. Distinguish code-confirmed bugs from risks requiring runtime reproduction.

## Code-confirmed problems to fix

1. **Export selection mismatch.** `CrosshairsPage._on_export_clicked()` creates a filename from `_selected_style_id` but emits only a path via `export_pack_requested`. `MainWindow` forwards that to `app.py`, which connects it to `export_current_style()`. Consequently, previewing B while A is active exports A under B's filename. Route the explicit selected style ID to the appropriate controller export action; do not change the active overlay just to export. Check exported file contents, not just the filename.
2. **My Crosshairs filters ignored.** `_matches_folder()` returns early for `_quick_view == 'my'`, ignoring `_folder_id`. Apply the My subset and the selected folder filter together, or expose a deliberately different filter set. Ensure selected chips accurately describe results, including Favorites, Creator, Imports, and Custom.
3. **Detail back navigation loses context.** Detail Back always navigates to `crosshairs`, and detail navigation always highlights Library, even when opened from My Crosshairs. Remember the source view and preserve search, filter, and scroll context on return.
4. **Stale preview cache.** `CrosshairCardButton` defaults to a cache key based on style ID, dimensions, and a constant render version. `sync_definition()` changes the definition without invalidating the cache. Include rendering-relevant style content in the key or invalidate it when style content changes. Bound the cache and handle device pixel ratio changes.
5. **Custom card states do not follow the theme.** Selected/batch colors are hardcoded dark blues while text still comes from the palette; active and selected border colors are hardcoded rather than accent tokens. Unify QPainter and QSS theme sources. Add distinct non-color cues for active, previewed, favorite, and batch selection, with visible hover and keyboard focus. The card paints its label manually: provide an accessible name and full-name tooltip.
6. **Chevron keyboard activation.** `ChevronButton` emits its action only in `mouseReleaseEvent`, instead of using the standard button clicked signal. Connect native activation so Space/Enter and mouse work consistently; do not trigger on a release outside the control.
7. **Invalid accent silently changes settings.** Settings replaces invalid input with a default purple and emits it. Retain the last valid value, show a useful validation message, and avoid applying invalid input. Ensure arbitrary allowed accents produce readable button text and focus states.

## Risks to reproduce and address

- Fixed drawer geometry (`width=360`, `y=166`, `height=max(260, page height-190)`) can obscure cards and become inaccessible at small sizes or larger text. Prefer layout-managed space or a responsive drawer with accessible scrolling and Escape dismissal. Verify interruption and resize during drawer animations.
- Gallery clears widgets on each keystroke and resize, uses `pop(0)` for pending items, and leaves grid row minimum heights from previous populations. Verify empty trailing space after reducing a large result set, scroll jumps, and flicker. Debounce search, reset stale constraints, and avoid unnecessary rebuilds while maintaining responsive batching.
- Favorite buttons have fixed 28x28 geometry but inherit generic button padding/minimums. Baseline rendering shows narrow tall outlines. Inspect effective QSS and provide a dedicated compact icon-button style.
- Permanent whole-page opacity effects and per-navigation animation objects may cause painting cost, retained objects, and abrupt rapid-navigation behavior. Ensure interrupted animations reach a consistent final state and completed animations/effects are cleaned up.
- Home and Settings have no outer scroll area. Creator and sidebar contain dense fixed arrangements. Verify all controls are reachable at 980x600 and Windows 125/150/200% scaling; test long labels and paths. Do not resolve clipping simply by raising the minimum window size.
- Programmatic slider setters can emit user-change signals; verify redundant writes and feedback loops. Use signal blocking where appropriate.
- QSS contains web-only properties such as `text-transform` and `letter-spacing`. Verify supported Qt properties and eliminate stylesheet warnings.

## Visual direction

Build a polished precision tool for gamers with a calm, compact Windows desktop aesthetic. Keep light, dark, system theme, and configurable accent. Use neutral layered surfaces, restrained accent, readable Segoe UI typography, consistent icons, subtle borders, and a deliberate spacing scale. Reduce oversized promotional headers, verbose explanatory copy, nested cards, and repeated purple gradients. Give the actual crosshair previews and creator canvas more room.

Use clear hierarchy: page title, compact task toolbar, primary content, contextual controls. Make the sidebar quieter, readable, and usable at minimum height. Preserve tooltips and accessible names when collapsed. Show concise overlay state and active crosshair context. Give Library a useful search/filter toolbar, adaptive grid, result count, intentional empty states, and clear selection actions. Let Creator prioritize the canvas with grouped tools, secondary previews, clear undo/redo, and one primary save action. Group Settings into readable sections and distinguish destructive maintenance actions.

Centralize colors, typography sizes, radii, spacing conventions, and state styles in the existing theme/component architecture. QPainter widgets must receive the same theme values as standard widgets. Avoid ornamental charts, fake data, unnecessary web fonts, glow, and decorative motion. Use short native animations (roughly 120–220 ms) where they explain a state change; respect reduced-motion preferences where available and provide a fallback preference if needed.

## Implementation and verification

This prompt covers migration, design, existing feature parity, and UI bug fixes. New runtime features are specified separately in GPT6_LUNA_FEATURES_PROMPT.md; do not bundle the AI feature expansion into this migration.

Work in stages: fix behavior, consolidate theme/components, redesign shell/library, improve remaining pages, then verify the full app. Keep the controller contract intact except for deliberate bug fixes updated at both ends. Run syntax/import checks with `.venv\Scripts\python.exe`. Use focused Qt tests for meaningful regressions: exporting B while A remains active; My view plus folder filtering; correct detail return route; cache invalidation after style changes; keyboard chevron activation. Write exports only into temporary directories.

Exercise all pages in light/dark/system themes and multiple accents; collapsed/expanded sidebar; minimum/default/large window sizes; DPI scaling; keyboard-only operation; rapid repeated navigation; search with no matches; favorites; multi-select/export; import cancellation; live detail editing; creator save/export and undo/redo; settings validation; game profile dialogs; zoom gating; and close-to-tray behavior. Do not modify real user library data or run installers for testing. Capture comparable before/after screenshots with readable text, and inspect the actual images. Offscreen tests cannot establish real Windows DPI, hotkey, tray, or overlay behavior: report any untested paths precisely.

Update the UI audit to match the implemented app and provide a concise final report of the design changes, bugs fixed, validation performed, remaining limitations, and screenshot locations. Do not claim every UI bug is fixed from a compile check alone. Continue until the implemented scope and checks are complete; do not stop after making only a prompt, plan, or cosmetic color change.

