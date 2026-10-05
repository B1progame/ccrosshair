from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crosshair_overlay import runtime_bootstrap


class FrozenQtRuntimeTests(unittest.TestCase):
    def test_foreign_icu_is_removed_but_unrelated_tools_are_kept(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "bundle"
            pyside = bundle / "PySide6"
            shiboken = bundle / "shiboken6"
            poppler = root / "poppler"
            tools = root / "tools"
            for directory in (pyside, shiboken, poppler, tools):
                directory.mkdir(parents=True)
            (poppler / "icuuc.dll").touch()
            old_path = os.environ.get("PATH", "")
            old_frozen = getattr(runtime_bootstrap.sys, "frozen", None)
            old_meipass = getattr(runtime_bootstrap.sys, "_MEIPASS", None)
            had_frozen = hasattr(runtime_bootstrap.sys, "frozen")
            had_meipass = hasattr(runtime_bootstrap.sys, "_MEIPASS")
            try:
                os.environ["PATH"] = os.pathsep.join((str(poppler), str(tools)))
                runtime_bootstrap.sys.frozen = True
                runtime_bootstrap.sys._MEIPASS = str(bundle)
                with patch.object(runtime_bootstrap.os, "add_dll_directory", create=True, return_value=object()):
                    runtime_bootstrap.configure_frozen_qt_runtime()
                entries = os.environ["PATH"].split(os.pathsep)
                self.assertNotIn(str(poppler), entries)
                self.assertIn(str(tools), entries)
                self.assertEqual(entries[:3], [str(bundle), str(pyside), str(shiboken)])
            finally:
                os.environ["PATH"] = old_path
                if had_frozen:
                    runtime_bootstrap.sys.frozen = old_frozen
                else:
                    del runtime_bootstrap.sys.frozen
                if had_meipass:
                    runtime_bootstrap.sys._MEIPASS = old_meipass
                else:
                    del runtime_bootstrap.sys._MEIPASS


if __name__ == "__main__":
    unittest.main()
