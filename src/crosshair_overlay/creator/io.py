from __future__ import annotations

import json
from pathlib import Path

from .models import CreatorCrosshair


def save_creator_crosshair(model: CreatorCrosshair, destination: Path) -> None:
    model.touch()
    destination.write_text(json.dumps(model.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")


def load_creator_crosshair(source: Path) -> CreatorCrosshair:
    payload = json.loads(source.read_text(encoding="utf-8"))
    return CreatorCrosshair.from_dict(payload)
