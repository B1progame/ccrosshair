from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from .app_settings import AppSettings
from .storage_paths import StoragePaths


class ConfigManager:
    def __init__(self) -> None:
        roaming = os.environ.get("APPDATA")
        self._app_dir = (Path(roaming) if roaming else Path.home() / "AppData" / "Roaming") / "CrosshairOverlay"
        self._settings_file = self._app_dir / "settings.json"
        self._crosshair_dir = self._app_dir / "crosshairs"
        self._storage = StoragePaths(self._crosshair_dir)
        self.last_load_warning = ""
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
            settings = self._read_settings(self._settings_file)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            self._preserve_corrupt_settings()
            try:
                settings = self._read_settings(self.backup_path)
                self.last_load_warning = f"Settings were recovered from {self.backup_path.name}. Review the recovered settings before continuing."
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                settings = AppSettings()
                self.last_load_warning = "Settings could not be read. Defaults are active; the damaged file was preserved for recovery."

        if not settings.crosshair_storage_path:
            settings.crosshair_storage_path = str(self._crosshair_dir)
        StoragePaths(Path(settings.crosshair_storage_path)).ensure()
        return settings

    def save(self, settings: AppSettings) -> None:
        self.backup_current_settings()
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._settings_file.parent,
                prefix=f"{self._settings_file.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                json.dump(settings.to_dict(), handle, ensure_ascii=True, indent=2)
            os.replace(temporary, self._settings_file)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @property
    def backup_path(self) -> Path:
        return self._settings_file.with_suffix(self._settings_file.suffix + ".bak")

    def backup_current_settings(self) -> bool:
        """Refresh the backup only when the current settings file is valid."""
        if not self._settings_file.exists():
            return False
        try:
            self._read_settings(self._settings_file)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            self._preserve_corrupt_settings()
            return False
        temporary = self.backup_path.with_suffix(self.backup_path.suffix + ".tmp")
        try:
            shutil.copy2(self._settings_file, temporary)
            os.replace(temporary, self.backup_path)
            return True
        finally:
            temporary.unlink(missing_ok=True)

    def _read_settings(self, path: Path) -> AppSettings:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Settings file must contain a JSON object.")
        return AppSettings.from_dict(raw)

    def _preserve_corrupt_settings(self) -> Path | None:
        if not self._settings_file.exists():
            return None
        target = self._settings_file.with_name("settings.corrupt.json")
        if target.exists():
            return target
        try:
            shutil.copy2(self._settings_file, target)
            return target
        except OSError:
            return None
