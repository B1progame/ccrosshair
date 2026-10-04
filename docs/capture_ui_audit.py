"""Render UI pages without starting overlays or touching user settings."""
import os
import sys
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from crosshair_overlay.app_settings import BetaZoomSettings
from crosshair_overlay.crosshairs.catalog import build_builtin_catalog
from crosshair_overlay.theme_manager import ThemeManager
from crosshair_overlay.ui.main_window import MainWindow

app = QApplication([])
ThemeManager(app).apply('dark', '#A923E2')
window = MainWindow(build_builtin_catalog(), 'classic_cross', 100, 'dark',
                    '#A923E2', 100, str(root), True, False, False,
                    BetaZoomSettings(), False)
window.show()
output = root / 'docs' / 'ui-audit'
output.mkdir(exist_ok=True)
for page in ('home', 'crosshairs', 'settings', 'creator'):
    window.navigate_to(page)
    QTest.qWait(600)
    window.grab().save(str(output / f'{page}.png'))
    print(f'{page}: {window.size().width()}x{window.size().height()}')
window.allow_close_once()
window.close()
