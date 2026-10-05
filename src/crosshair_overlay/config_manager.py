from __future__ import annotations

import json
import hashlib
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

    def preview_backup(self, current: AppSettings) -> dict[str, object]:
        """Return a privacy-safe, field-group preview of the settings backup."""
        if not self.backup_path.exists():
            return {"available": False, "reason": "No settings backup is available."}
        try:
            raw = self.backup_path.read_bytes()
            backup = self._read_settings(self.backup_path)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {"available": False, "reason": "The settings backup is invalid and was left untouched."}
        before, after = current.to_dict(), backup.to_dict()
        groups = {
            "Interface and appearance": ("theme_mode", "accent_color", "selected_size_percent", "global_size_percent"),
            "Crosshair and overlay": ("selected_style_id", "overlay_enabled", "auto_enable_on_fullscreen"),
            "Zoom": ("beta_zoom",),
            "Game profiles and loadouts": ("game_profiles", "auto_switch_game_profiles"),
            "Input-reactive behavior": ("reactive", "quick_switch_next_hotkey", "quick_switch_previous_hotkey", "quick_switch_favorite_hotkey"),
            "Library organization": ("favorite_style_ids", "recent_style_ids", "recent_crosshair_colors", "library_collections", "library_tags"),
            "Accessibility": ("accessibility",),
            "Startup preferences": ("auto_update_on_startup", "run_on_startup_tray"),
        }
        changed = [label for label, keys in groups.items() if any(before.get(key) != after.get(key) for key in keys)]
        stat = self.backup_path.stat()
        return {
            "available": True,
            "fingerprint": hashlib.sha256(raw).hexdigest(),
            "modified": stat.st_mtime_ns,
            "changedGroups": changed,
            "summary": {
                "games": len(backup.game_profiles),
                "collections": len(backup.library_collections),
                "favorites": len(backup.favorite_style_ids),
                "zoomMode": backup.beta_zoom.runtime_mode,
                "overlayEnabled": backup.overlay_enabled,
            },
        }

    def restore_backup(self, current: AppSettings, expected_fingerprint: str) -> AppSettings:
        """Restore only the backup the user previewed, keeping current settings as the new backup."""
        preview = self.preview_backup(current)
        if not preview.get("available") or preview.get("fingerprint") != expected_fingerprint:
            raise ValueError("The settings backup changed after preview. Review it again before restoring.")
        restored = self._read_settings(self.backup_path)
        self.save(restored)
        return restored

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
