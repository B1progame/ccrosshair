from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
        return {
            "format": "crosshair-overlay-creator-v2",
            "version": int(self.version),
            "name": self.name,
            "grid_size": int(self.grid_size),
            "creation_mode": self.creation_mode,
            "color_hex": self.color_hex.upper(),
            "filled_cells": [[x, y] for x, y in self.normalized_cells()],
            "style_id": self.style_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

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
        )
        model.filled_cells = model.normalized_cells()
        return model
