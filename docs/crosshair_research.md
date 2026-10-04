# Crosshair Research Notes

## Scope
This project phase reviewed public crosshair ecosystems and grouped design patterns into reusable renderer families.

Research source categories included:
- Crosshair overlay communities (Crosshair X style tools and preset communities)
- Pro FPS databases (VALORANT, CS2)
- Counter-Strike crosshair setting documentation
- Hero-shooter reticle customization references (Overwatch and Marvel Rivals)
- Minecraft custom crosshair resource packs (dot, square, plus, bracket, scope styles)

## Primary Source Links
- https://crosshair-x.com/
- https://prosettings.net/tools/valorant-crosshair-database/
- https://prosettings.net/blog/best-valorant-crosshair-codes/
- https://prosettings.net/tools/cs2-crosshair-database/
- https://counterstrike.fandom.com/wiki/Crosshair
- https://liquipedia.net/counterstrike/Crosshair
- https://www.pcgamer.com/overwatch-2-how-to-change-crosshair/
- https://game8.co/games/Overwatch2/archives/393117
- https://crosshaircanvas.com/overwatch/how-to-change-crosshair
- https://crosshaircanvas.com/overwatch/best-crosshair
- https://www.polygon.com/marvel-rivals-guide/497404/crosshair-codes-best-how-to-change-reticle
- https://www.curseforge.com/minecraft-bedrock/texture-packs/custom-crosshairs-3
- https://www.curseforge.com/minecraft-bedrock/addons/custom-crosshairs
- https://www.curseforge.com/minecraft/texture-packs/pvp-crosshair-v3
- https://modrinth.com/resourcepack/vanilla-collective-plus-square-dot-crosshair
- https://modrinth.com/resourcepack/dotted-crosshair
- https://modrinth.com/resourcepack/square-crosshair-quel13s-pack
- https://modrinth.com/resourcepack/voiddot-cpvp-crosshair

## Family Taxonomy Used In App
- Dot
- Classic
- Ring / Circle
- Bracket
- Square
- Diamond
- Target / Scope
- Minecraft / PvP
- Creator Grid

## Commonly Customizable Parameters Found Across Sources
- color
- thickness
- line length or overall size
- center gap
- center dot and dot size
- opacity/alpha
- outline and outline thickness
- t-style (hide top arm)
- rotation (in some reticle systems)

## Mapping Strategy
1. Group references into families by geometry, not by game title.
2. Implement one renderer per family with parameterized defaults.
3. Create many presets by varying defaults (size/gap/thickness/dot/outline).
4. Keep settings metadata with each preset so detail UI only exposes supported options.
5. Serialize both built-ins and custom variants using a shared plugin-friendly format.

## Artifacts
- `docs/crosshair_reference_catalog.json`: structured reference dataset (50+ cataloged variants)
- Built-in families and presets: `src/crosshair_overlay/crosshairs/catalog.py`
- Plugin format and I/O: `src/crosshair_overlay/crosshairs/io.py`

## Notes
The dataset is a classification reference for design families and feature patterns; it is intentionally normalized so renderer logic can be reused for many presets.
