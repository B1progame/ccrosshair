"""Load the app's locally authored, offline pixel-crosshair expansion."""
from __future__ import annotations

import json
from pathlib import Path

from ..config import OverlayShape, OverlayStyle
from .models import CrosshairDefinition


MANIFEST_PATH = Path(__file__).resolve().parents[1] / "assets" / "catalog" / "original_expansion.json"


def load_original_expansion(path: Path = MANIFEST_PATH) -> list[CrosshairDefinition]:
    """Return validated custom-grid styles from the packaged provenance manifest."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != 1 or not isinstance(payload.get("presets"), list):
        raise ValueError("Unsupported original crosshair catalog manifest")

    definitions: list[CrosshairDefinition] = []
    seen_ids: set[str] = set()
    seen_geometry: set[tuple[tuple[int, int], ...]] = set()
    for item in payload["presets"]:
        style_id = item.get("id")
        cells_raw = item.get("cells")
        if not isinstance(style_id, str) or not style_id or style_id in seen_ids:
            raise ValueError("Invalid or duplicate crosshair catalog id")
        if item.get("gridSize") != 32 or not isinstance(cells_raw, list) or not cells_raw:
            raise ValueError(f"Invalid custom-grid geometry for {style_id}")
        cells: list[tuple[int, int]] = []
        for point in cells_raw:
            if (not isinstance(point, list) or len(point) != 2
                    or any(not isinstance(axis, int) or isinstance(axis, bool) for axis in point)
                    or any(axis < 0 or axis >= 32 for axis in point)):
                raise ValueError(f"Invalid custom-grid cell for {style_id}")
            cells.append((point[0], point[1]))
        geometry = tuple(sorted(set(cells), key=lambda point: (point[1], point[0])))
        if len(geometry) != len(cells) or geometry in seen_geometry:
            raise ValueError(f"Duplicate custom-grid geometry for {style_id}")
        seen_ids.add(style_id)
        seen_geometry.add(geometry)
        style = OverlayStyle(
            style_id=style_id,
            display_name=str(item.get("name") or style_id),
            shape=OverlayShape.CUSTOM_GRID,
            color_rgba=(255, 255, 255, 255),
            custom_grid_size=32,
            custom_filled_cells=geometry,
            custom_cell_size=1,
            center_dot=False,
        )
        tags = item.get("tags", [])
        aliases = item.get("aliases", [])
        if not isinstance(tags, list) or not all(isinstance(value, str) for value in tags):
            raise ValueError(f"Invalid tags for {style_id}")
        if not isinstance(aliases, list) or not all(isinstance(value, str) for value in aliases):
            raise ValueError(f"Invalid aliases for {style_id}")
        category = item.get("category", "practical")
        definitions.append(CrosshairDefinition(
            style=style,
            family=str(item.get("family") or "Original"),
            description=f"Original {category} pixel crosshair, included offline.",
            tags=tuple(tags),
            editable_settings=(),
            source_type="original_catalog",
            aliases=tuple(aliases),
            origin_game=str(item.get("gameAssociation") or "Generic FPS"),
            author=str(item.get("author") or "Original Crosshair Overlay design"),
            source_url=str(item.get("sourceUrl") or ""),
            reuse_status=str(item.get("reuseStatus") or "original locally authored geometry"),
            approximate=bool(item.get("approximate", False)),
            catalog_version=int(payload.get("schemaVersion", 1)),
        ))
    return definitions
