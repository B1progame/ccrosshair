# Prompt 2 — GPT-6 Luna: feature expansion, AI zoom, and performance

Work in C:\Users\bslid.BENJI-PC\OneDrive\Dokumente\BENJI\APPS\crosshair\v1. Implement the features below using the actual current architecture. If prompt 1 has been completed, the React control UI communicates through the typed bridge while Python/PySide6 owns the overlays, capture, input, storage, and AI workers. Extend that contract; do not recreate a second settings UI or migrate frameworks again. If the migration has not happened, adapt to the existing native UI. This is a separate runtime-feature assignment, not a second visual redesign.

Inspect repository instructions, current diffs, README, dependencies, app.py, app_settings.py, config.py, zoom_overlay_window.py, overlay_window.py, crosshair_widget.py, overlay_renderer.py, crosshairs/, creator/, game_services.py, windows_runtime.py, and current bridge/frontend code if present. Preserve every existing working flow and file format. Do not invent APIs or treat the historical UI audit as current. Existing name search and static presets already exist; extend them accurately.

Use find-skills at C:\Users\bslid.BENJI-PC\.agents\skills\find-skills\SKILL.md, ui-ux-pro-max at C:\Users\bslid.BENJI-PC\.codex\skills\ui-ux-pro-max\SKILL.md, Desktop UI Design at C:\Users\bslid.BENJI-PC\.codex\skills\desktop-ui-design\SKILL.md, and relevant verification/performance guidance. GSAP at C:\Users\bslid.BENJI-PC\.agents\skills\gsap-core\SKILL.md applies to React control UI effects; native crosshair/zoom rendering must remain independent from JavaScript timing.

## FIRST: preserve the current project on GitHub before implementation

The user explicitly authorizes creating a recoverable checkpoint and updating GitHub main BEFORE any migration or feature implementation. First perform read-only checks: repository instructions, git status including untracked files, current branch, origin URL, diff, ignored project assets, and remote main after fetch. Expected repository is https://github.com/B1progame/ccrosshair.git and the observed local branch was main; verify both again. Do not reset, clean, discard, stash away, or overwrite current work. Inspect changes for credentials/private data before staging; stage intended source and configuration explicitly rather than blindly adding everything. Preserve existing edits, including modifications made by another active chat.

Commit the current project state, including relevant untracked source/configuration. docs/ is currently ignored: explicitly add the two prompt Markdown files and any important project documentation using narrowly scoped git add -f paths, or a narrow ignore exception. Review ignored source assets/build configuration needed to reproduce the app and include them selectively. Do not commit .venv, caches, generated binaries, private user libraries, secrets, or huge model weights. Git checkpoints do not back up ignored user data: explain what is excluded and create a separate local backup of any user data that the implementation will migrate.

Create a uniquely named backup branch and annotated tag from that exact checkpoint commit (e.g. backup/pre-react-migration-<timestamp> or backup/pre-feature-expansion-<timestamp>), and push those named refs to origin. Update remote main with the checkpoint using a normal fast-forward push. If remote main has diverged, preserve the local checkpoint first, then integrate remote changes without discarding either side, commit any resolved merge, and run baseline checks; never force push or rewrite main. If conflicts need a substantive product decision, ask that specific question instead of guessing. Respect branch protection: create a checkpoint PR if direct updates are blocked, attach it to this chat, and wait for main to include the checkpoint before starting implementation. Do not claim a PR alone satisfies the requested main update.

Verify git ls-remote for remote main, backup branch, and tag; record the full commit IDs and a working GitHub commit link. Report any baseline failures without hiding them. If authentication/network/protection prevents the remote checkpoint, stop implementation and explain the exact blocker. Do not proceed solely on a local commit when the requested GitHub checkpoint is missing.

Only after the remote checkpoint is verified, create a codex/ implementation branch and start work. Future rollback should use the backup ref in a separate checkout or a reviewed revert commit, not destructive reset/force push. Do not merge finished implementation into main without a later explicit request. At the start of each prompt independently, checkpoint its own current baseline; when prompt 2 follows prompt 1, preserve the completed migration too. If implementation branches are unmerged, preserve their work and do not switch away or merge them into main without explaining the branch state and obtaining the necessary decision.

## Feature requirements


### Research and skill selection

Use `find-skills` for desktop Qt, Python performance, computer vision, local inference, and regression testing. Add the installed `C:\Users\bslid.BENJI-PC\.agents\skills\verification-before-completion\SKILL.md` to the selected guidance. Check any additional skill's real contents, source, install count, and repository reputation before adopting it. Do not invent a skill name or treat a web-video generation skill as a live-inference skill.

The preparation for this prompt checked the [skills directory](https://skills.sh/) and searched for PySide6/ONNX skills. The CLI search produced no usable output before it was stopped; external candidates were not sufficiently vetted to recommend installation. Use the installed desktop/design/verification skills above plus primary technical documentation as the current fallback. If finding a better skill is possible, verify it before use; an unsuccessful search must not stop the task.

Primary research starting points, checked while preparing this prompt on 2026-10-04:

- [Windows screen capture](https://learn.microsoft.com/en-us/windows/apps/develop/media-authoring-processing/screen-capture): supported capture workflow; check actual capture availability and limitations.
- [ONNX Runtime DirectML](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html): a Windows GPU inference candidate; compare current providers and hardware compatibility before selecting one.
- [ONNX Runtime super-resolution example](https://onnxruntime.ai/docs/tutorials/mobile/superres.html): reference model/inference workflow, not evidence of Windows gameplay throughput.
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN): practical restoration models to benchmark; no assumption of real-time performance on this machine.
- [LaMa](https://github.com/advimman/lama): image-inpainting research baseline; not a verified low-latency game-crosshair remover.

Verify current APIs, dependencies, model weight licenses, packaging constraints, and official game documentation during implementation. Record the exact model/checkpoint/hash and hardware used for results. Do not make up throughput from paper titles or marketing claims.

### 1. Excellent live zoom and local AI upscaling

Current code: `app.py` uses a 33 ms Qt timer and `_capture_zoom_pixmap()` calls `QScreen.grabWindow()` on a small crop; `zoom_overlay_window.py` scales the pixmap with Qt SmoothTransformation. This is conventional magnification, not AI upscaling. The crop enforces a minimum of 18 pixels and zoom has a minimum factor of 2. Reinspect the current code because edits may have occurred since this analysis.

Build a genuinely responsive zoom pipeline. Support incremental zoom in/out while zoom is active, configurable wheel/key bindings, hold/toggle modes, reset-to-default, stable center anchoring, and smooth changes without restarting the window entrance animation every frame. Default controls must not steal mouse wheel input from gameplay; make input consumption an explicit preference. Offer useful presets such as 2x/4x/8x/16x where supported, and clearly show the effective maximum rather than silently saturating at the crop floor. Increasing magnification must always sample the original capture, never repeatedly upscale an already enhanced image. Zoom does not create more truthful source detail.

Offer Fast, Balanced, and Quality modes. Fast must work without downloading an AI model. Balanced/Quality should optionally use a verified lightweight local super-resolution model after benchmarks show a benefit. Compare ordinary interpolation/sharpening and at least one small AI model. Use a larger restoration model only if measured latency and quality warrant it. Cloud inference is unsuitable as the default live pipeline.

Separate capture, inference, and presentation behind interfaces. Keep QWidget operations and QPixmap creation/use on the GUI thread; use worker-safe image/buffer representations in workers. Use a bounded latest-frame queue, timestamps, cancellation/session generations, reusable buffers, model warmup, and no backlog. Ignore late results after zoom closes, monitor switches, or settings change. Stop capture/inference when unused; degrade gracefully if GPU/model initialization fails. Do not repeatedly load weights or launch a new process per frame.

Benchmark supported native capture backends against the current Qt capture. Handle mixed DPI, negative monitor coordinates, game-client bounds, window resize, HDR/color conversion where supported, and capture exclusion. Verify that neither the zoom window nor the app crosshair feeds back into capture. Respect capture denial and unsupported fullscreen modes; never disguise a stale image as live. Keep latency more important than invented detail and suppress temporal shimmer/ghosting. Prefer spatial inference first; temporal reconstruction requires actual alignment and scene-cut handling.

Expose actual backend, model, capture resolution, output FPS, p50/p95 end-to-end frame age, dropped frames, and resource use in a compact diagnostics view. Treat 30 FPS with p95 latency below 75 ms as an initial Balanced-mode target to test on stated hardware, not a promised capability. Pursue 60 FPS only if the total capture/inference/presentation budget allows it. Measure gameplay FPS/frame time impact with AI on/off. Set quality budgets from evidence and show the fallback honestly.

### 2. Much larger researched crosshair library

Research common crosshair families and documented presets from multiple games and primary sources where possible: precise dots, open/closed crosses, T shapes, rings, ring-dot combinations, brackets, chevrons, sniper guides, and distinctive creator designs. Include player-named presets only when the attribution and settings are sourced, with a checked date. Do not promise to add 'all crosshairs': the set is open-ended and constantly changing. Instead establish a useful coverage matrix and target at least 100 meaningfully distinct presets after counting the existing catalog. Color-only clones must not inflate the count.

Use small structured definitions and reusable rendering primitives instead of hundreds of handwritten paint branches. Add source URL, origin game, author attribution if applicable, license/reuse status, aliases, tags, and version metadata without breaking old packs. Match parameterized shape geometry accurately; mark approximate conversions. Keep the catalog usable offline. Do not scrape entire third-party sites or redistribute asset packs without checking reuse permission.

Search by display name already exists in `CrosshairsPage._filtered_items()` along with family, description, source type, and tags. Preserve it and extend it to aliases, game, and attributed player/creator names. Support case-insensitive partial matching, sensible token matching, filters, sorting, result count, favorites, recent usage, and fast reset. Keep search/filter state when opening a detail view. Never claim search is new when it is already implemented. Validate duplicates and malformed definitions.

### 3. Better crosshair color and appearance controls

Distinguish app accent from crosshair color. Provide live color preview, RGBA/hex entry with validation, palette swatches, recent colors, outline color/thickness, opacity, and per-profile persistence. Show previews on light, dark, and textured backgrounds. Ensure export/import preserves appearance exactly and that library preview caches refresh after edits.

Optional adaptive contrast should sample a small region at a capped rate, use hysteresis to avoid flicker, and support manual locking. Clearly distinguish automatic contrast from cosmetic color cycling. Keep visibility and accurate center alignment more important than spectacle.

### 4. Input-reactive crosshair animations

Add configurable fire pulse, gap expansion/recovery, opacity pulse, and optional ADS/hold-to-hide behavior. Provide duration, amplitude, recovery, firing cadence, and reduced-motion/static preferences per profile. Render from a shared animation state, using monotonic elapsed time so frame drops do not change animation duration. Keep the crosshair centered and avoid clipping expanded shapes.

Start with configurable foreground-only mouse/key observation using supported OS input APIs, without injecting input or reading game memory. An input click is an attempted fire action, not proof a weapon fired; ammo, reload, menus, firing mode, and game bindings can differ. Call this input-reactive mode and provide a sandbox preview. Support rebinding and cancellation on focus loss. Never claim input-based expansion measures actual recoil or weapon accuracy.

Actual gameplay events may be used only through a documented game-provided telemetry/mod/plugin integration, with per-game capabilities. Native crosshair export through a game's supported settings may integrate compatible static designs, but arbitrary app animations cannot automatically become engine-rendered crosshairs. Avoid process-memory reads, DLL injection, graphics hooking, anti-cheat bypass, or undocumented game-file patching. Document limitations of supported integrations rather than pretending there is universal integration.

### 5. Removing a game's built-in crosshair: feasibility and honest delivery

The desired outcome is to remove the game crosshair completely without reading or modifying the game. Treat this seriously, but distinguish what can actually be achieved:

- **True removal:** use the game's own documented crosshair/HUD visibility setting or a supported integration. Research per-game instructions and expose a capability matrix. Do not report unsupported games as supported or silently alter game configuration.
- **AI reconstruction:** screen capture sees the final composited pixels; it has no access to the original scene hidden beneath the crosshair. Inpainting predicts plausible pixels and changes only the app's processed output. It cannot erase a crosshair from the game's framebuffer. A desktop patch placed over the game would still be an overlay and would not satisfy the user's explicit non-overlay requirement. Therefore do not implement such a patch as 'complete removal.'

Build an experimental cleanup mode INSIDE the existing processed zoom view, clearly named 'Reconstruct captured crosshair area (experimental)', if feasible. Start with a manually calibrated small mask for a configured game crosshair; automatic detection may come later. Preserve all unmasked pixels, limit the region, process cleanup before upscaling, and apply temporal consistency only with real motion validation. Compare a simple fast fill baseline with a lightweight local inpainting candidate; LaMa is a research reference, not the predetermined runtime model. Add mask preview, strength, disable/reset, and confidence/abstention behavior. Handle dynamic crosshair bloom, outlines, scene cuts, rapid movement, and other HUD elements.

Never present reconstructed pixels as recovered ground truth or imply hidden targets can be reliably recovered. Disable cleanup or show the original capture when the mask or reconstruction is unreliable. Use synthetic gameplay-like scenes with known clean pixels and motion sequences to quantify masked-region reconstruction error, unmasked pixel preservation, latency, and flicker. Do not declare the user's true non-overlay removal requirement achieved by this prototype. If no supported native mechanism exists, report that specific requirement as technically blocked under the stated constraints while completing independent features.

### 6. Additional useful features

Implement modest high-value additions alongside the main work: profile-based zoom/appearance/animation settings; quick preset switching; center-offset calibration and multi-monitor selection; an emergency hide/disable hotkey; import/export round-trip validation; a preview sandbox for backgrounds, colors, and animation; and a compact performance/compatibility page. Keep these focused and avoid unrelated product expansion. Larger ideas such as community sync, a cloud marketplace, or automatic model training belong in a documented backlog.

### 7. Staging and acceptance

First recheck the current code and baseline timings. Fix feature-blocking UI behavior while preserving the visual design from prompt 1. Expand/validate the catalog and improve search/appearance controls. Add and verify input-reactive animations. Stabilize continuous non-AI zoom. Benchmark and integrate optional local upscaling. Finally prototype captured-image cleanup and add documented per-game native crosshair-disable guidance. If prompt 1 already completed the visual redesign, verify parity and proceed directly to feature work; do not redesign it again.

For UI/library performance, benchmark 100, 1,000, and 10,000 definitions with long names and mixed shapes. Prefer model/view virtualization and a delegate if widget-per-card creation fails those benchmarks. Measure search response time, GUI-thread stalls, memory/cache bounds, first useful paint, idle CPU, and active-animation cost. Avoid animating all offscreen gallery cards. Proposed goals: results appear within 150 ms after debounce on 1,000 definitions and steady interaction avoids GUI stalls above 50 ms on stated hardware. Report measurements and adjust architecture rather than fabricating success.

Use focused regression tests for queue bounds, stale-frame rejection, zoom crop bounds/anchoring, cancellation, catalog/search correctness, export identity, style-cache invalidation, color persistence, animation timing, and focus loss. For AI quality tests use known clean references and moving sequences rather than judging one screenshot. Compare original, conventional, and AI results side by side with the same source frames. Validate optional dependency installation in the project environment, offline fallback, missing weights, model versioning, packaging, and clean shutdown. Verify model downloads/checksums and require explicit enablement before large downloads; never download model weights merely to write this prompt.

Deliver before/after UI screenshots, a coverage count and source manifest for the catalog, a hardware-specific performance table, implemented integration capabilities, and precise experimental/blocked requirements. Clearly separate implemented and tested features from prototypes and future ideas. Do not promise universal game support, infinite true detail, guaranteed zero latency, or true native crosshair removal through captured-pixel prediction.

## More features with clear priorities

Required additions beyond the core feature list:

1. **Named loadouts and quick switching:** multiple crosshair/zoom/animation loadouts per game, user-rebindable next/previous/favorite shortcuts, quick-switch palette, and automatic switching using existing foreground game detection. Preserve a manual override and restore the prior profile on leaving the game. Report ambiguous matches.
2. **ADS visibility profiles:** hold/toggle ADS input mode, separate hip-fire/ADS appearances, hide-on-ADS option, and configurable transition. Label input-driven behavior accurately; do not claim weapon-state detection.
3. **Creator productivity:** mirror/rotate, grid snapping, layered shape primitives, templates, duplicate, undo/redo, dirty-state indication, crash-recoverable autosave, and recovery preview. Define a backward-compatible extension for layers and flatten on export to older formats when needed.
4. **Preset comparison and calibration:** compare 2–4 presets on identical backgrounds, pixel-aligned center offset, per-monitor calibration, and scaling/aspect-ratio preview. Keep native and frontend renderers consistent at odd/even sizes and fractional DPI.
5. **Library organization:** collections/tags, duplicate detection, recently used, favorite ordering, bulk tagging/export, deterministic sorting, and import preview with conflict choices (keep/replace/duplicate). Never silently overwrite an existing definition.
6. **Configuration resilience:** versioned settings migrations, automatic backups before migration/reset, restore-preview UI, atomic writes, and recovery from malformed configuration. Avoid erasing a valid backup when recovery fails.
7. **Useful accessibility:** fully keyboard-operable profile switching and creator controls, color-vision-friendly palettes, high-contrast mode, adjustable control UI density/text size, and a static/reduced-motion mode affecting both React and native animation.
8. **Runtime modes:** explicit Quiet/Eco/Balanced/Quality presets controlling preview cadence, capture size, inference budget, and idle behavior. Thermal/GPU-load adaptation should use hysteresis, retain a manual lock, and expose what changed. Changing modes must not secretly alter crosshair geometry.
9. **Local diagnostics export:** opt-in export of timings, backend/model versions, sanitized errors, and configuration summary; exclude captured game frames, usernames, paths, and secrets by default. Add a preview before saving the report.
10. **Compatibility checks:** guided monitor/capture/backend tests, clear supported fullscreen/borderless modes, and per-game native crosshair-hide instructions with source/check date. Do not equate a successful desktop demo with universal game compatibility.

Optional stretch work after the required scope passes: a local screenshot-to-preset assistant (user-provided image, crop/threshold/vectorize preview, adjustable conversion), shareable preset codes, and a local recorded-frame benchmark runner. These must not delay core UI parity, zoom quality, or measured performance. Document unsupported cases; no cloud accounts, marketplaces, or game automation expansion without a separate request.

## React/native integration acceptance

When the hybrid UI exists, implement each new setting in the Python schema, validation, persistence/migrations, bridge types/commands/events, React UI, and import/export as applicable. Ensure the bridge reconnects to a complete snapshot, pending commands fail cleanly on reload, rapid changes coalesce without losing the final state, and changing profiles during inference cancels old-session results. Keep AI/capture frames outside the configuration bridge. Test the installed offline application as well as the Vite mock/dev experience. Do not claim mock-adapter screenshots prove native functionality.

## Delivery

Use a coverage matrix marking required features as implemented/tested, implemented/unverified, experimental, or blocked with a specific reason. Include benchmark hardware, workload, frame-age metrics, gameplay impact, screenshots, source/model manifest, and remaining limitations. Complete feasible required work rather than silently treating all features as a wishlist. Genuine technical limits (especially non-overlay game crosshair removal) must be reported precisely while independent work continues.
