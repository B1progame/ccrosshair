# Crosshair Overlay (Windows, PySide6)

A desktop crosshair overlay app with a multi-page UI, live overlay updates, a creator grid editor, and a plugin-ready crosshair library.

## Run
1. `setup.bat`
2. `start.bat`

Or manually:
1. `python -m venv .venv`
2. `.venv\Scripts\python.exe -m pip install -r requirements.txt`
3. `.venv\Scripts\python.exe main.py`

## Storage
Default storage path:
- `%APPDATA%\CrosshairOverlay\crosshairs`

Config path:
- `%APPDATA%\CrosshairOverlay\settings.json`

## Crosshair Formats
### `.xhair` (plugin-ready single crosshair)
JSON file with:
- `format`: `crosshair-overlay-xhair-v1`
- `style`: serialized overlay shape + parameters
- `family`, `description`, `tags`
- `editable_settings`
- metadata such as `source_type`

### `.xpack` (plugin-ready bundle)
JSON file with:
- `format`: `crosshair-overlay-xpack-v1`
- `crosshairs`: array of `.xhair` payloads

### Compatibility
The app also imports legacy formats:
- `.chpack`
- `.chgrid`

## Crosshair Research Process
Research references and taxonomy are documented in:
- `docs/crosshair_research.md`
- `docs/crosshair_reference_catalog.json`

The dataset captures:
- source link
- family/type
- visual features
- grid vs vector style
- common parameters
- app mapping target

## How To Research More Crosshairs
1. Search by family keywords: `dot`, `ring`, `bracket`, `square`, `scope`, `t-style`, `pixel pvp crosshair`.
2. Pull from multiple ecosystems:
   - FPS databases (VALORANT/CS2)
   - hero shooter reticle pages
   - Minecraft resource-pack ecosystems
   - overlay community galleries
3. Record each finding in `docs/crosshair_reference_catalog.json` with consistent fields.
4. Classify by geometry first (family), not by game title.

## How To Add More Built-in Crosshairs
1. Open `src/crosshair_overlay/crosshairs/catalog.py`.
2. Add a preset via `_make(...)` with:
   - `style_id`, `display_name`, `family`
   - renderer shape
   - default style params
   - `editable_settings`
3. Reuse existing families whenever possible; only create a new renderer family if geometry is truly new.

## How To Add A New Renderer Family
1. Add a new `OverlayShape` entry in `src/crosshair_overlay/config.py`.
2. Implement draw logic in `src/crosshair_overlay/overlay_renderer.py`.
3. Add presets in `catalog.py` and choose supported settings metadata.

## How To Add Plugin Packs
### Single crosshair plugin
- Drop `.xhair` into the storage folder.

### Bundle plugin
- Drop `.xpack` into the storage folder.
- Each entry is loaded into the crosshair library.

## Detail Editing Flow
- Open `Crosshairs` page.
- Select a crosshair.
- Click `Open Detail`.
- Edit supported controls (only those declared for that preset).
- Overlay updates live.
- Save as variant or export `.xhair`.
