from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re


def slugify_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    cleaned = cleaned.strip("-_")
    return cleaned or "crosshair"


@dataclass(frozen=True)
class StoragePaths:
    root: Path

    @property
    def custom_dir(self) -> Path:
        return self.root / "custom"

    @property
    def creator_dir(self) -> Path:
        return self.root / "creator"

    @property
    def imports_dir(self) -> Path:
        return self.root / "imports"

    @property
    def exports_dir(self) -> Path:
        return self.root / "exports"

    @property
    def legacy_dir(self) -> Path:
        return self.root / "legacy"

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.custom_dir.mkdir(parents=True, exist_ok=True)
        self.creator_dir.mkdir(parents=True, exist_ok=True)
        self.imports_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.legacy_dir.mkdir(parents=True, exist_ok=True)

    def custom_definition_path(self, style_id: str) -> Path:
        return self.custom_dir / f"{slugify_name(style_id)}.xhair"

    def creator_definition_path(self, style_id: str) -> Path:
        return self.creator_dir / f"{slugify_name(style_id)}.chgrid"

    def create_import_bundle(self, label: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = self.imports_dir / f"{slugify_name(label)}_{stamp}"
        target.mkdir(parents=True, exist_ok=True)
        (target / "items").mkdir(parents=True, exist_ok=True)
        return target
