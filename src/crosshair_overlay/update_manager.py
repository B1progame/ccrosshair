from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .app_metadata import (
    APP_EXE_NAME,
    APP_NAME,
    APP_VERSION,
    GITHUB_API_VERSION,
    GITHUB_LATEST_RELEASE_API,
    GITHUB_LATEST_RELEASE_URL,
    INSTALLER_ASSET_PREFIX,
    INSTALLER_ASSET_SUFFIX,
)


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag_name: str
    name: str
    html_url: str
    published_at: str
    body: str
    installer_asset: ReleaseAsset | None


class UpdateManager:
    CHUNK_SIZE = 1024 * 256

    def current_version(self) -> str:
        return APP_VERSION

    def can_self_update(self) -> bool:
        executable = Path(sys.executable)
        return bool(getattr(sys, "frozen", False) and executable.suffix.lower() == ".exe")

    def install_directory(self) -> Path | None:
        if not self.can_self_update():
            return None
        return Path(sys.executable).resolve().parent

    def current_executable(self) -> Path | None:
        if not self.can_self_update():
            return None
        return Path(sys.executable).resolve()

    def releases_page_url(self) -> str:
        return GITHUB_LATEST_RELEASE_URL

    def fetch_latest_release(self, timeout_s: float = 8.0) -> ReleaseInfo:
        request = urllib.request.Request(
            GITHUB_LATEST_RELEASE_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": APP_NAME,
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise UpdateError(f"GitHub returned HTTP {exc.code} while checking releases.") from exc
        except urllib.error.URLError as exc:
            raise UpdateError("Could not reach GitHub to check for updates.") from exc
        except json.JSONDecodeError as exc:
            raise UpdateError("GitHub returned an unreadable release response.") from exc

        version = self._normalize_version(str(payload.get("tag_name", "")).strip() or str(payload.get("name", "")).strip())
        asset = self._pick_installer_asset(payload.get("assets", []))
        return ReleaseInfo(
            version=version,
            tag_name=str(payload.get("tag_name", "")).strip(),
            name=str(payload.get("name", "")).strip(),
            html_url=str(payload.get("html_url", "")).strip() or GITHUB_LATEST_RELEASE_URL,
            published_at=str(payload.get("published_at", "")).strip(),
            body=str(payload.get("body", "")).strip(),
            installer_asset=asset,
        )

    def is_newer_than_current(self, release: ReleaseInfo) -> bool:
        return self._version_key(release.version) > self._version_key(self.current_version())

    def download_installer(
        self,
        release: ReleaseInfo,
        progress_callback=None,
    ) -> Path:
        asset = release.installer_asset
        if asset is None:
            raise UpdateError("The latest GitHub release does not include a Windows installer asset.")

        target_dir = Path(tempfile.gettempdir()) / "CrosshairOverlayUpdater"
        target_dir.mkdir(parents=True, exist_ok=True)
        destination = target_dir / asset.name
        temp_destination = destination.with_suffix(destination.suffix + ".part")

        request = urllib.request.Request(
            asset.download_url,
            headers={
                "User-Agent": APP_NAME,
                "Accept": "application/octet-stream",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30.0) as response:
                total_size = response.headers.get("Content-Length")
                expected = int(total_size) if total_size and total_size.isdigit() else asset.size or 0
                downloaded = 0
                with temp_destination.open("wb") as handle:
                    while True:
                        chunk = response.read(self.CHUNK_SIZE)
                        if not chunk:
                            break
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback is not None:
                            progress_callback(downloaded, expected)
            if expected and downloaded != expected:
                raise UpdateError("The installer download was incomplete; please try again.")
        except UpdateError:
            temp_destination.unlink(missing_ok=True)
            raise
        except urllib.error.HTTPError as exc:
            temp_destination.unlink(missing_ok=True)
            raise UpdateError(f"GitHub returned HTTP {exc.code} while downloading the installer.") from exc
        except urllib.error.URLError as exc:
            temp_destination.unlink(missing_ok=True)
            raise UpdateError("Could not download the installer from GitHub.") from exc
        except OSError as exc:
            temp_destination.unlink(missing_ok=True)
            raise UpdateError("Could not save the downloaded installer locally.") from exc
        except Exception as exc:
            temp_destination.unlink(missing_ok=True)
            raise UpdateError("The installer download was interrupted; please try again.") from exc

        try:
            temp_destination.replace(destination)
        except OSError as exc:
            temp_destination.unlink(missing_ok=True)
            raise UpdateError("Could not finalize the downloaded installer.") from exc
        return destination

    def schedule_silent_update(self, installer_path: Path) -> None:
        install_dir = self.install_directory()
        current_executable = self.current_executable()
        if install_dir is None or current_executable is None:
            raise UpdateError("Automatic installer updates only work from an installed app build.")

        script_path = Path(tempfile.gettempdir()) / "CrosshairOverlayUpdater" / "run_update.cmd"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script = self._update_script(
            current_pid=os.getpid(),
            installer_path=installer_path.resolve(),
            install_dir=install_dir.resolve(),
            current_executable=current_executable.resolve(),
        )
        script_path.write_text(script, encoding="utf-8")
        subprocess.Popen(["cmd.exe", "/c", str(script_path)], creationflags=subprocess.CREATE_NO_WINDOW)

    def _pick_installer_asset(self, assets: object) -> ReleaseAsset | None:
        if not isinstance(assets, list):
            return None
        for raw_asset in assets:
            if not isinstance(raw_asset, dict):
                continue
            name = str(raw_asset.get("name", "")).strip()
            if not name.startswith(INSTALLER_ASSET_PREFIX) or not name.lower().endswith(INSTALLER_ASSET_SUFFIX):
                continue
            download_url = str(raw_asset.get("browser_download_url", "")).strip()
            if not download_url:
                continue
            size = int(raw_asset.get("size", 0) or 0)
            return ReleaseAsset(name=name, download_url=download_url, size=size)
        return None

    def _normalize_version(self, raw: str) -> str:
        text = raw.strip()
        if text.lower().startswith("v"):
            text = text[1:]
        return text or "0.0.0"

    def _version_key(self, raw: str) -> tuple[int, ...]:
        matches = re.findall(r"\d+", self._normalize_version(raw))
        if not matches:
            return (0,)
        return tuple(int(item) for item in matches)

    def _update_script(self, current_pid: int, installer_path: Path, install_dir: Path, current_executable: Path) -> str:
        installer_arg = self._escape_cmd_argument(installer_path)
        install_dir_arg = self._escape_cmd_argument(install_dir)
        current_executable_arg = self._escape_cmd_argument(current_executable)
        return "\n".join(
            [
                "@echo off",
                "setlocal EnableExtensions",
                f"set \"TARGET_PID={current_pid}\"",
                f"set \"INSTALLER={installer_arg}\"",
                f"set \"INSTALL_DIR={install_dir_arg}\"",
                f"set \"APP_EXE={current_executable_arg}\"",
                ":wait_for_app",
                "tasklist /FI \"PID eq %TARGET_PID%\" | find \"%TARGET_PID%\" >nul",
                "if not errorlevel 1 (",
                "    timeout /t 1 /nobreak >nul",
                "    goto wait_for_app",
                ")",
                "start \"\" /wait \"%INSTALLER%\" /SP- /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER /CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS /DIR=\"%INSTALL_DIR%\"",
                "if exist \"%APP_EXE%\" start \"\" \"%APP_EXE%\"",
                "del \"%INSTALLER%\" >nul 2>nul",
                "del \"%~f0\" >nul 2>nul",
            ]
        )

    def _escape_cmd_argument(self, path: Path) -> str:
        return str(path).replace('"', '""')
