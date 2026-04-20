from __future__ import annotations

import json
from pathlib import Path

from .app_settings import AppSettings
from .storage_paths import StoragePaths


class ConfigManager:
    def __init__(self) -> None:
        self._app_dir = Path.home() / "AppData" / "Roaming" / "CrosshairOverlay"
        self._settings_file = self._app_dir / "settings.json"
        self._crosshair_dir = self._app_dir / "crosshairs"
        self._storage = StoragePaths(self._crosshair_dir)
        self._app_dir.mkdir(parents=True, exist_ok=True)
        self._storage.ensure()

    @property
    def settings_path(self) -> Path:
        return self._settings_file

    @property
    def default_crosshair_path(self) -> Path:
        return self._crosshair_dir

    @property
    def storage_paths(self) -> StoragePaths:
        return self._storage

    def load(self) -> AppSettings:
        if not self._settings_file.exists():
            settings = AppSettings(crosshair_storage_path=str(self._crosshair_dir))
            self.save(settings)
            return settings

        try:
            raw = json.loads(self._settings_file.read_text(encoding="utf-8"))
            settings = AppSettings.from_dict(raw)
        except (OSError, json.JSONDecodeError):
            settings = AppSettings()

        if not settings.crosshair_storage_path:
            settings.crosshair_storage_path = str(self._crosshair_dir)
        StoragePaths(Path(settings.crosshair_storage_path)).ensure()
        return settings

    def save(self, settings: AppSettings) -> None:
        self._settings_file.write_text(
            json.dumps(settings.to_dict(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
