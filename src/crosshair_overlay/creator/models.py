from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class CreatorLayer:
    layer_id: str
    name: str
    primitive: str = "draw"
    visible: bool = True
    filled_cells: list[tuple[int, int]] = field(default_factory=list)

    def normalized_cells(self, grid_size: int) -> list[tuple[int, int]]:
        maximum = grid_size - 1
        return sorted({(max(0, min(maximum, int(x))), max(0, min(maximum, int(y)))) for x, y in self.filled_cells}, key=lambda cell: (cell[1], cell[0]))

    def to_dict(self, grid_size: int) -> dict:
        return {"id": self.layer_id, "name": self.name, "primitive": self.primitive, "visible": bool(self.visible),
                "filled_cells": [[x, y] for x, y in self.normalized_cells(grid_size)]}


@dataclass
class CreatorCrosshair:
    name: str
    grid_size: int
    color_hex: str
    filled_cells: list[tuple[int, int]]
    creation_mode: str = "draw"
    style_id: str = ""
    version: int = 2
    created_at: str = ""
    updated_at: str = ""
    layers: list[CreatorLayer] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.creation_mode = self.creation_mode if self.creation_mode in {"draw", "pixel"} else "draw"
        if not self.created_at:
            self.created_at = _utc_now_iso()
        if not self.updated_at:
            self.updated_at = _utc_now_iso()

    def touch(self) -> None:
        self.updated_at = _utc_now_iso()

    def normalized_cells(self) -> list[tuple[int, int]]:
        if self.layers:
            return sorted({cell for layer in self.layers if layer.visible for cell in layer.normalized_cells(self.grid_size)}, key=lambda cell: (cell[1], cell[0]))
        result: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        max_idx = self.grid_size - 1
        for x, y in self.filled_cells:
            cx = max(0, min(max_idx, int(x)))
            cy = max(0, min(max_idx, int(y)))
            key = (cx, cy)
            if key not in seen:
                seen.add(key)
                result.append(key)
        result.sort(key=lambda cell: (cell[1], cell[0]))
        return result

    def to_dict(self) -> dict:
        payload = {
            "format": "crosshair-overlay-creator-v3" if self.layers else "crosshair-overlay-creator-v2",
            "version": 3 if self.layers else int(self.version),
            "name": self.name,
            "grid_size": int(self.grid_size),
            "creation_mode": self.creation_mode,
            "color_hex": self.color_hex.upper(),
            "filled_cells": [[x, y] for x, y in self.normalized_cells()],
            "style_id": self.style_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.layers:
            payload["layers"] = [layer.to_dict(self.grid_size) for layer in self.layers[:32]]
        return payload

    @classmethod
    def from_dict(cls, data: dict) -> "CreatorCrosshair":
        cells_raw = data.get("filled_cells", [])
        cells: list[tuple[int, int]] = []
        if isinstance(cells_raw, list):
            for cell in cells_raw:
                if isinstance(cell, list) and len(cell) == 2:
                    cells.append((int(cell[0]), int(cell[1])))

        model = cls(
            name=str(data.get("name", "Unnamed Crosshair")),
            grid_size=max(8, min(64, int(data.get("grid_size", 32)))),
            creation_mode=str(data.get("creation_mode", "draw")),
            color_hex=str(data.get("color_hex", "#FFFFFF")).upper(),
            filled_cells=cells,
            style_id=str(data.get("style_id", "")),
            version=int(data.get("version", 2)),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            layers=cls._layers_from_data(data.get("layers"), max(8, min(64, int(data.get("grid_size", 32))))),
        )
        model.filled_cells = model.normalized_cells()
        return model

    @staticmethod
    def _layers_from_data(raw: object, grid_size: int) -> list[CreatorLayer]:
        if not isinstance(raw, list):
            return []
        layers: list[CreatorLayer] = []
        seen: set[str] = set()
        allowed_primitives = {"draw", "cross", "dot", "ring", "bracket"}
        for item in raw[:32]:
            if not isinstance(item, dict):
                continue
            layer_id = str(item.get("id", "")).strip()[:64]
            name = str(item.get("name", "Layer")).strip()[:64]
            primitive = item.get("primitive", "draw")
            visible = item.get("visible", True)
            raw_cells = item.get("filled_cells", [])
            if not layer_id or layer_id in seen or not name or not isinstance(primitive, str) or primitive not in allowed_primitives or not isinstance(visible, bool) or not isinstance(raw_cells, list) or len(raw_cells) > 4096:
                continue
            cells = []
            for cell in raw_cells:
                if isinstance(cell, list) and len(cell) == 2 and all(type(value) is int for value in cell):
                    cells.append((cell[0], cell[1]))
            seen.add(layer_id)
            layer = CreatorLayer(layer_id, name, primitive, visible, cells)
            layer.filled_cells = layer.normalized_cells(grid_size)
            layers.append(layer)
        return layers
