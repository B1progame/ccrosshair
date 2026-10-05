from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


class CreatorCanvasUiTests(unittest.TestCase):
    def test_drag_paints_a_continuous_stroke_in_the_native_creator(self) -> None:
        script = r"""
import json, sys
import crosshair_overlay
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from crosshair_overlay.app import AppController
from crosshair_overlay.ui.react_surface import register_react_scheme
register_react_scheme()
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
controller = AppController(app, start_to_tray=False)
controller.start()
surface = controller._main_window._react_surface
def finish(state):
    print(json.dumps(state), flush=True)
    controller.quit_application()
def fail(message):
    finish({"error": message})
def begin(ok):
    if not ok:
        fail("React page did not load")
        return
    surface._page.runJavaScript("document.querySelector('.nav[aria-label=\\\"Creator\\\"]')?.click()", lambda _: QTimer.singleShot(350, draw))
def draw():
    script = "(()=>{const canvas=document.querySelector('.creator-canvas');if(!canvas)return JSON.stringify({error:'Creator canvas did not render'});const rect=canvas.getBoundingClientRect();const send=(type,fraction,buttons)=>canvas.dispatchEvent(new PointerEvent(type,{bubbles:true,cancelable:true,pointerId:17,pointerType:'mouse',isPrimary:true,button:0,buttons,clientX:rect.left+rect.width*fraction,clientY:rect.top+rect.height*fraction}));send('pointerdown',.25,1);send('pointermove',.75,1);send('pointerup',.75,0);return 'drawing'})()"
    surface._page.runJavaScript(script, lambda value: (surface._page.runJavaScript("window.__drawResult="+json.dumps(value)), QTimer.singleShot(350, inspect)))
def inspect():
    surface._page.runJavaScript("JSON.stringify({count:document.querySelectorAll('.creator-canvas .cell.filled').length,layer:document.querySelector('.creator-layer-row small')?.textContent,canvas:!!document.querySelector('.creator-canvas'),page:document.querySelector('.page-head h1')?.textContent,result:window.__drawResult})", lambda raw: finish(json.loads(raw) if isinstance(raw,str) else raw))
surface.load_finished.connect(begin)
QTimer.singleShot(10000, lambda: (fail("Creator UI smoke timed out"), app.exit(2)))
raise SystemExit(app.exec())
"""
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path("src").resolve())
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
        environment.pop("QTWEBENGINE_CHROMIUM_FLAGS", None)
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=16,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(result.stdout.splitlines()[-1])
        self.assertNotIn("error", state, result.stdout)
        self.assertGreaterEqual(state["count"], 10, result.stdout)


if __name__ == "__main__":
    unittest.main()
