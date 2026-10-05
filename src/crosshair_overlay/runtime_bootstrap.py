from __future__ import annotations

import os
import sys
from pathlib import Path


_DLL_DIRECTORY_HANDLES: list[object] = []


def _contains_foreign_qt_runtime(directory: Path) -> bool:
    """Return true when a PATH entry can shadow this app's Qt/ICU runtime."""
    direct_names = (
        "Qt5Core.dll", "Qt6Core.dll", "Qt5Gui.dll", "Qt6Gui.dll",
        "Qt5Widgets.dll", "Qt6Widgets.dll", "QtCore.pyd",
        "pyside6.abi3.dll", "shiboken6.abi3.dll", "icuuc.dll", "icuin.dll",
    )
    try:
        if any((directory / name).is_file() for name in direct_names):
            return True
        return any(directory.glob("icuuc*.dll")) or any(directory.glob("icuin*.dll")) or any(
            directory.glob("icudt*.dll")
        )
    except OSError:
        return False


def configure_frozen_qt_runtime() -> None:
    """Configure stable WebEngine rendering and prefer bundled frozen Qt."""
    # The UI is a static React surface; Chromium GPU composition adds no
    # benefit here and can leave QWebEngineView completely black when D3D
    # shared-image contexts are lost. Keep this process-level setting before
    # QtWebEngine is imported so Chromium starts in its reliable software path.
    if sys.platform.startswith("win"):
        chromium_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        if "--disable-gpu" not in chromium_flags.split():
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{chromium_flags} --disable-gpu".strip()

    if not getattr(sys, "frozen", False):
        return

    bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    pyside_root = bundle_root / "PySide6"
    bundled_qt_dirs = {bundle_root.resolve(), pyside_root.resolve(), (bundle_root / "shiboken6").resolve()}
    retained_path: list[str] = []
    for raw_directory in os.environ.get("PATH", "").split(os.pathsep):
        if not raw_directory:
            continue
        directory = Path(raw_directory)
        try:
            is_bundled = directory.resolve() in bundled_qt_dirs
        except OSError:
            is_bundled = False
        if not is_bundled and _contains_foreign_qt_runtime(directory):
            continue
        retained_path.append(raw_directory)
    # Keep the app's Qt directories first, then all unrelated host tools so
    # optional commands such as nvidia-smi remain discoverable.
    os.environ["PATH"] = os.pathsep.join(
        [str(bundle_root), str(pyside_root), str(bundle_root / "shiboken6"), *retained_path]
    )

    for directory in (bundle_root, pyside_root, bundle_root / "shiboken6"):
        if directory.is_dir() and hasattr(os, "add_dll_directory"):
            try:
                _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(directory)))
            except OSError:
                continue

    plugins = pyside_root / "plugins"
    if plugins.is_dir():
        os.environ["QT_PLUGIN_PATH"] = str(plugins)
        platform_plugins = plugins / "platforms"
        if platform_plugins.is_dir():
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_plugins)
