# Offline catalog manifest

Reviewed 2026-10-05. The current catalog contains 100 geometry-distinct original generic presets generated from shared shape primitives. Current distribution: classic crosses 30, brackets 14, rings 13, dots 11, chevrons 8, sniper guides 8, circle crosses 7, squares 5, diamonds 4. The exact count and unique geometry signatures are checked in `tests/test_catalog_features.py`.

| Family | Representation | Source / attribution |
|---|---|---|
| Precision dots | dot geometry, size and optional center mark | Original generic patterns; no player attribution |
| Open, closed and T crosses | four-arm geometry, gap, thickness, rotation and T-style | Original generic patterns; no player attribution |
| Rings and ring-dot | circle radius/thickness and optional center mark | Original generic patterns; no player attribution |
| Brackets | corner geometry with size/gap/weight variants | Original generic patterns; no player attribution |
| Chevrons | native chevron primitive and scale variants | Original generic patterns; no player attribution |
| Sniper guides | native guide primitive and scale variants | Original generic patterns; no player attribution |
| Squares, diamonds and focus reticles | reusable shape primitives and parameter variants | Original generic patterns; no player attribution |

No player-named preset is included: no primary source proving both attribution and exact settings was verified. The definition schema preserves `source_url`, `origin_game`, `author`, aliases, reuse status, approximation flag and catalog version. The current generic entries use the VALORANT patch notes as a reference for crosshair configuration concepts, not as a claim that the shapes are copied from VALORANT. Patterns are marked original and are not copied game assets.

Primary references checked 2026-10-05:

- [VALORANT Patch Notes 5.04](https://playvalorant.com/en-us/news/game-updates/valorant-patch-notes-5-04/) documents crosshair customization controls and separate profiles.
- [Counter-Strike update feed](https://www.counter-strike.net/news/updates?l=english) is the primary update source; it is not used to claim a verified preset or hide-crosshair capability.

Coverage is intentionally finite and does not claim to include every game or player crosshair.
