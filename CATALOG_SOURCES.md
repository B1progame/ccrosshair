# Offline catalog manifest

Reviewed 2026-10-05. The catalog retains the 100 original v1.2.3 presets and adds 210 locally authored, offline-ready pixel designs: 150 practical reticles across 15 families and 60 novelty/joke designs. All 310 catalog geometries are distinct. The generated source and provenance manifest ship at `src/crosshair_overlay/assets/catalog/original_expansion.json`; `tools/generate_crosshair_expansion.py` regenerates it from `tests/fixtures/catalog_baseline_v1.2.3.json`.

| Family | Representation | Source / attribution |
|---|---|---|
| Precision dots | dot geometry, size and optional center mark | Original generic patterns; no player attribution |
| Open, closed and T crosses | four-arm geometry, gap, thickness, rotation and T-style | Original generic patterns; no player attribution |
| Rings and ring-dot | circle radius/thickness and optional center mark | Original generic patterns; no player attribution |
| Brackets | corner geometry with size/gap/weight variants | Original generic patterns; no player attribution |
| Chevrons | native chevron primitive and scale variants | Original generic patterns; no player attribution |
| Sniper guides | native guide primitive and scale variants | Original generic patterns; no player attribution |
| Squares, diamonds and focus reticles | reusable shape primitives and parameter variants | Original generic patterns; no player attribution |
| Practical pixel reticles (open cross, segmented ring, brackets, chevrons, diamond, scope, radial, aperture, rangefinder and related families) | 32×32 `CUSTOM_GRID` native pixel geometry | Original locally authored patterns; no player attribution |
| Novelty/joke reticles (faces, animals, food, objects, symbols) | 32×32 `CUSTOM_GRID` native pixel geometry | Original locally authored patterns; no player attribution |

No player-named preset is included: no primary source proving both attribution and exact settings was verified. The definition schema preserves `source_url`, `origin_game`, `author`, aliases, reuse status, approximation flag and catalog version. The current generic entries use the VALORANT patch notes as a reference for crosshair configuration concepts, not as a claim that the shapes are copied from VALORANT. Patterns are marked original and are not copied game assets.

Primary and reference material checked 2026-10-05:

- [VALORANT Patch Notes 4.05](https://playvalorant.com/en-us/news/game-updates/valorant-patch-notes-4-05/) documents import/export of crosshair settings.
- [VALORANT Patch Notes 5.04](https://playvalorant.com/en-us/news/game-updates/valorant-patch-notes-5-04/) documents independent horizontal and vertical crosshair controls.
- [VCRDB FAQ](https://www.vcrdb.net/faq) was checked for catalog/API provenance; its API is not public, and its presets were not copied.
- [CS2 Crosshair](https://www.cs2crosshair.org/) informed broad geometry-family coverage only. No player names or exact settings are attributed to these patterns.
- [Counter-Strike update feed](https://www.counter-strike.net/news/updates?l=english) is the primary update source; it is not used to claim a verified preset or hide-crosshair capability.

Original designs use an empty source URL and explicitly identify their local authorship. Coverage is finite and does not claim to include every game or player crosshair. The v1.2.3 baseline IDs are preserved, and the test suite verifies distinct geometry, native pixel rendering, search tags, and serialization round trips.
