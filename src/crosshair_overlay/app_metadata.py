from __future__ import annotations

from pathlib import Path


APP_NAME = "Crosshair Overlay"
APP_EXE_NAME = "CrosshairOverlay.exe"
GITHUB_OWNER = "B1progame"
GITHUB_REPO = "ccrosshair"
GITHUB_API_VERSION = "2026-03-10"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
GITHUB_LATEST_RELEASE_URL = f"{GITHUB_RELEASES_URL}/latest"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
INSTALLER_ASSET_PREFIX = "CrosshairOverlay-Setup-"
INSTALLER_ASSET_SUFFIX = ".exe"


def load_app_version() -> str:
    version_file = Path(__file__).with_name("version.txt")
    try:
        text = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"
    return text or "0.0.0"


APP_VERSION = load_app_version()
