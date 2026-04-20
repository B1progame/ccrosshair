from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiscoveredGame:
    game_id: str
    title: str
    source: str
    executable_path: str
    executable_name: str
    icon_path: str


def scan_game_libraries() -> list[DiscoveredGame]:
    items: list[DiscoveredGame] = []
    items.extend(_scan_steam_games())
    items.extend(_scan_epic_games())

    deduped: dict[str, DiscoveredGame] = {}
    for game in items:
        if game.game_id not in deduped:
            deduped[game.game_id] = game
    return sorted(deduped.values(), key=lambda item: (item.source, item.title.lower()))


def _scan_steam_games() -> list[DiscoveredGame]:
    games: list[DiscoveredGame] = []
    for library in _steam_library_paths():
        steamapps = library / "steamapps"
        if not steamapps.exists():
            continue
        for manifest in sorted(steamapps.glob("appmanifest_*.acf")):
            text = _safe_read_text(manifest)
            if not text:
                continue
            app_id = _extract_vdf_field(text, "appid")
            name = _extract_vdf_field(text, "name")
            install_dir_name = _extract_vdf_field(text, "installdir")
            if not app_id or not name or not install_dir_name:
                continue
            install_dir = steamapps / "common" / install_dir_name
            executable = _detect_primary_executable(install_dir)
            executable_name = executable.name.lower() if executable else ""
            executable_path = str(executable) if executable else ""
            games.append(
                DiscoveredGame(
                    game_id=f"steam:{app_id}",
                    title=name,
                    source="steam",
                    executable_path=executable_path,
                    executable_name=executable_name,
                    icon_path=executable_path,
                )
            )
    return games


def _scan_epic_games() -> list[DiscoveredGame]:
    games: list[DiscoveredGame] = []
    program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    manifest_root = Path(program_data) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    if not manifest_root.exists():
        return games

    for item_file in sorted(manifest_root.glob("*.item")):
        raw = _safe_read_text(item_file)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        title = str(data.get("DisplayName") or data.get("AppName") or item_file.stem).strip()
        app_name = str(data.get("AppName") or item_file.stem).strip()
        install_path = Path(str(data.get("InstallLocation", "")).strip())
        launch_executable = str(data.get("LaunchExecutable", "")).strip()
        executable = _resolve_epic_executable(install_path, launch_executable)
        executable_name = executable.name.lower() if executable else ""
        executable_path = str(executable) if executable else ""
        games.append(
            DiscoveredGame(
                game_id=f"epic:{app_name.lower()}",
                title=title,
                source="epic",
                executable_path=executable_path,
                executable_name=executable_name,
                icon_path=executable_path,
            )
        )
    return games


def _resolve_epic_executable(install_path: Path, launch_executable: str) -> Path | None:
    if launch_executable:
        candidate = Path(launch_executable)
        if not candidate.is_absolute():
            candidate = install_path / candidate
        if candidate.exists() and candidate.suffix.lower() == ".exe":
            return candidate
    return _detect_primary_executable(install_path)


def _steam_library_paths() -> list[Path]:
    roots: list[Path] = []
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    for candidate in (
        Path(program_files_x86) / "Steam",
        Path(program_files) / "Steam",
        Path(local_app_data) / "Steam",
    ):
        if candidate.exists():
            roots.append(candidate)

    libraries: list[Path] = []
    for root in roots:
        libraries.append(root)
        library_file = root / "steamapps" / "libraryfolders.vdf"
        text = _safe_read_text(library_file)
        if not text:
            continue
        for match in re.finditer(r'"path"\s*"([^"]+)"', text):
            raw = match.group(1).replace("\\\\", "\\").strip()
            path = Path(raw)
            if path.exists():
                libraries.append(path)

    unique: list[Path] = []
    seen: set[str] = set()
    for path in libraries:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _detect_primary_executable(install_dir: Path) -> Path | None:
    if not install_dir.exists():
        return None

    candidates: list[Path] = []
    candidates.extend(sorted(install_dir.glob("*.exe")))
    candidates.extend(sorted(install_dir.glob("*/*.exe")))

    if not candidates:
        for idx, candidate in enumerate(install_dir.rglob("*.exe")):
            candidates.append(candidate)
            if idx >= 120:
                break

    if not candidates:
        return None

    blacklist = ("unins", "crash", "report", "launcher", "eac", "easyanticheat", "installer", "setup")

    def score(path: Path) -> tuple[int, int, int]:
        name = path.name.lower()
        flagged = 1 if any(part in name for part in blacklist) else 0
        depth = len(path.parts)
        return (flagged, depth, len(name))

    candidates.sort(key=score)
    return candidates[0]


def _extract_vdf_field(text: str, key: str) -> str:
    pattern = rf'"{re.escape(key)}"\s+"([^"]*)"'
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
