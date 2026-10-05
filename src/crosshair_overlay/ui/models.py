from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameRowModel:
    game_id: str
    title: str
    source: str
    executable_path: str
    icon_path: str
    assigned_style_id: str
    enabled: bool
    loadouts: list[dict]
    active_loadout_id: str
