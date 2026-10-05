from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


class ReactSchemeTests(unittest.TestCase):
    def test_zoom_ai_controls_are_visible_when_beta_preference_is_off(self) -> None:
        script = r"""
import json, sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget
from crosshair_overlay.ui.react_surface import ReactSurface, register_react_scheme
register_react_scheme()
app = QApplication(sys.argv)
host = QWidget()
surface = ReactSurface(host)
def inspect(ok):
    if not ok:
        app.exit(2)
        return
    surface._page.runJavaScript(
        "document.querySelector('.nav[aria-label=\\\"Zoom\\\"]')?.click()",
        lambda _value: QTimer.singleShot(250, read_page),
    )
def read_page():
    surface._page.runJavaScript(
        "JSON.stringify({text:document.querySelector('#root')?.innerText||'',locked:!!document.querySelector('.nav-locked')})",
        lambda value: (print(json.dumps(value), flush=True), app.quit()),
    )
surface.load_finished.connect(inspect)
QTimer.singleShot(8000, lambda: app.exit(3))
surface.start()
raise SystemExit(app.exec())
"""
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path("src").resolve())
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=15,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(result.stdout.splitlines()[-1])
        if isinstance(state, str):
            state = json.loads(state)
        self.assertFalse(state["locked"])
        self.assertIn("AI TOOLS", state["text"])
        self.assertIn("Quality · AI Super-Resolution 3×", state["text"])

    def test_custom_scheme_registers_with_a_valid_default_port_before_webengine(self) -> None:
        script = (
            "from crosshair_overlay.ui.react_surface import QWebEngineUrlScheme, register_react_scheme; "
            "register_react_scheme(); "
            "print(QWebEngineUrlScheme.schemeByName(b'crosshair').defaultPort())"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path("src").resolve())},
        )
        self.assertEqual(result.stdout.strip(), "80")
        self.assertNotIn("needs a default port", result.stderr)

    def test_bundled_react_page_loads_assets_and_mounts(self) -> None:
        script = r"""
import json, sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget
from crosshair_overlay.ui.react_surface import ReactSurface, register_react_scheme
register_react_scheme()
app = QApplication(sys.argv)
host = QWidget()
surface = ReactSurface(host)
def inspect(ok):
    if not ok:
        print('LOAD_FAILED', flush=True)
        app.exit(2)
        return
    def read_state():
        surface._page.runJavaScript(
            "document.querySelector('.nav[aria-label=\\\"Compatibility\\\"]')?.click()",
            lambda _value: QTimer.singleShot(250, read_compatibility),
        )
    def read_compatibility():
        surface._page.runJavaScript(
            "JSON.stringify({title:document.title,children:document.querySelector('#root')?.children.length||0,text:document.querySelector('#root')?.innerText||''})",
            lambda value: (print(json.dumps(value, ensure_ascii=True), flush=True), app.quit()),
        )
    QTimer.singleShot(1000, read_state)
surface.load_finished.connect(inspect)
QTimer.singleShot(8000, lambda: (print('LOAD_TIMEOUT', flush=True), app.exit(3)))
surface.start()
raise SystemExit(app.exec())
"""
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path("src").resolve())
        environment["QT_QPA_PLATFORM"] = "offscreen"
        # The task container restricts Chromium's nested sandbox process. Keep
        # this override confined to the test child, never the shipped app.
        environment["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=15,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(result.stdout.splitlines()[-1])
        if isinstance(state, str):
            state = json.loads(state)
        self.assertEqual(state["title"], "Crosshair Overlay")
        self.assertGreater(state["children"], 0)
        self.assertIn("Compatibility", state["text"])
        self.assertIn("Native settings guidance", state["text"])
        self.assertIn("Test monitor capture", state["text"])


if __name__ == "__main__":
    unittest.main()
