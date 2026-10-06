from __future__ import annotations

import unittest
from pathlib import Path

from crosshair_overlay.update_manager import UpdateManager


class UpdateManagerTests(unittest.TestCase):
    def test_update_script_shows_installer_progress_and_retains_installer_on_failure(self) -> None:
        manager = UpdateManager()
        script = manager._update_script(
            current_pid=4321,
            installer_path=Path(r"C:\Temp\CrosshairOverlayUpdater\CrosshairOverlay-Setup-1.5.3.exe"),
            install_dir=Path(r"C:\Users\Example\AppData\Local\Programs\Crosshair Overlay"),
            current_executable=Path(r"C:\Users\Example\AppData\Local\Programs\Crosshair Overlay\CrosshairOverlay.exe"),
            log_path=Path(r"C:\Temp\CrosshairOverlayUpdater\update.log"),
            setup_log_path=Path(r"C:\Temp\CrosshairOverlayUpdater\setup.log"),
        )

        self.assertIn("/SILENT", script)
        self.assertNotIn("/VERYSILENT", script)
        self.assertIn("/LOG=\"%SETUP_LOG%\"", script)
        self.assertIn("set \"INSTALLER_EXIT=%ERRORLEVEL%\"", script)
        self.assertIn("Installer failed with exit code %INSTALLER_EXIT%", script)
        self.assertIn("%APP_EXE%\"", script)
        self.assertLess(script.index("exit /b %INSTALLER_EXIT%"), script.index("del \"%INSTALLER%\""))
        self.assertIn("%UPDATE_LOG%", script)


if __name__ == "__main__":
    unittest.main()
