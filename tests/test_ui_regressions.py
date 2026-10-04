from __future__ import annotations

import json
import os
import tempfile
import unittest
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from crosshair_overlay.config import OverlayStyle
from crosshair_overlay.app import AppController
from crosshair_overlay.creator.models import CreatorCrosshair
from crosshair_overlay.crosshairs.catalog import build_builtin_catalog
from crosshair_overlay.crosshairs.io import save_xhair
from crosshair_overlay.storage_paths import StoragePaths
from crosshair_overlay.theme_manager import ThemeManager
from crosshair_overlay.ui.bridge_router import BridgeCommandRouter
from crosshair_overlay.ui.pages.crosshairs_page import CrosshairsPage
from crosshair_overlay.ui.pages.settings_page import SettingsPage
from crosshair_overlay.ui.sidebar import ChevronButton
from crosshair_overlay.widgets.crosshair_card import CrosshairCardButton


class UiRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.definitions = build_builtin_catalog()

    def make_page(self) -> CrosshairsPage:
        return CrosshairsPage(OrderedDict(self.definitions), "classic_cross", 100)

    def test_my_filters_intersect_the_my_collection(self) -> None:
        page = self.make_page()
        favorite = self.definitions["classic_cross"].with_favorite(True)
        imported = replace(self.definitions["dot_micro"], source_type="imported_pack")
        page._definitions = OrderedDict([(favorite.style_id, favorite), (imported.style_id, imported)])
        page._quick_view = "my"
        page._folder_id = "imports"
        self.assertEqual([item.style_id for item in page._filtered_items()], [imported.style_id])
        page._folder_id = "favorites"
        self.assertEqual([item.style_id for item in page._filtered_items()], [favorite.style_id])

    def test_single_style_export_emits_the_previewed_id_and_contents(self) -> None:
        page = self.make_page()
        page._selected_style_id = "dot_micro"
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "dot_micro.xhair"
            spy = QSignalSpy(page.export_pack_requested)
            page.export_pack_requested.connect(lambda style_id, path: save_xhair(self.definitions[style_id], Path(path)))
            with patch("crosshair_overlay.ui.pages.crosshairs_page.QFileDialog.getSaveFileName", return_value=(str(target), "")):
                page._on_export_clicked()
            self.assertEqual(spy.count(), 1)
            self.assertEqual(spy.at(0), ["dot_micro", str(target)])
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["style"]["style_id"], "dot_micro")

    def test_preview_cache_key_changes_when_style_content_changes(self) -> None:
        original = self.definitions["classic_cross"]
        card = CrosshairCardButton(original)
        card._preview_pixmap(80, 60)
        updated_style = OverlayStyle(**{**original.style.__dict__, "color_rgba": (255, 0, 0, 255)})
        card.sync_definition(original.with_style(updated_style))
        card._preview_pixmap(80, 60)
        self.assertEqual(len(CrosshairCardButton._preview_cache), 2)

    def test_sidebar_chevron_responds_to_space(self) -> None:
        button = ChevronButton()
        button.show()
        button.setFocus()
        spy = QSignalSpy(button.toggled_requested)
        QTest.keyClick(button, Qt.Key.Key_Space)
        self.assertEqual(spy.count(), 1)

    def test_invalid_accent_does_not_emit_or_replace_last_valid_value(self) -> None:
        settings = SettingsPage("dark", "#67D4AE", 100, "C:/tmp", False)
        spy = QSignalSpy(settings.accent_color_changed)
        settings._accent_input.setText("not-a-color")
        settings._on_accent_text_changed()
        self.assertEqual(spy.count(), 0)
        self.assertEqual(settings._last_valid_accent, "#67D4AE")
        self.assertFalse(settings._accent_error.isHidden())

    def test_bright_accent_gets_dark_button_text(self) -> None:
        manager = ThemeManager(self.app)
        self.assertEqual(manager._contrast_text("#FFFF00"), "#111615")
        self.assertEqual(manager._contrast_text("#223344"), "#FFFFFF")

    def test_catalog_query_is_bounded_for_ten_thousand_styles(self) -> None:
        class Window:
            def __init__(self) -> None:
                self._definitions = OrderedDict()

            @staticmethod
            def _style_payload(item):
                return {"id": item.style_id, "name": item.display_name}

        window = Window()
        for index in range(10_000):
            item = SimpleNamespace(
                style_id=f"style-{index}", display_name=f"Benchmark {index:05d}",
                family="Benchmark", source_type="custom" if index % 5 == 0 else "builtin",
                tags=("performance",), is_favorite=index % 7 == 0,
            )
            window._definitions[item.style_id] = item
        router = BridgeCommandRouter(window)
        result = router.dispatch("queryCatalog", {"query": "benchmark", "filter": "all", "page": 0, "pageSize": 36})
        self.assertEqual(result["total"], 10_000)
        self.assertEqual(len(result["styles"]), 36)
        match = router.dispatch("queryCatalog", {"query": "benchmark 09999", "filter": "all", "page": 0, "pageSize": 36})
        self.assertEqual(match["total"], 1)
        self.assertEqual(match["styles"][0]["id"], "style-9999")

    def test_catalog_query_rejects_oversized_pages(self) -> None:
        class Window:
            _definitions = OrderedDict()
        router = BridgeCommandRouter(Window())
        with self.assertRaises(ValueError):
            router.dispatch("queryCatalog", {"query": "", "filter": "all", "page": 0, "pageSize": 100_000})

    def test_new_creator_save_avoids_builtin_ids_and_existing_creator_is_updated(self) -> None:
        class ControllerHarness:
            _creator_style_id = AppController._creator_style_id
            _next_available_style_id = AppController._next_available_style_id
            _slugify = AppController._slugify

            def __init__(self, storage: Path) -> None:
                self._definitions = build_builtin_catalog()
                self._storage_paths = StoragePaths(storage)

        controller = ControllerHarness(Path(tempfile.gettempdir()) / "crosshair-creator-id-test")
        model = CreatorCrosshair("Classic Cross", 32, "#FFFFFF", [])
        self.assertEqual(controller._creator_style_id(model, model.name), "classic_cross_2")
        controller._definitions["creator_test"] = replace(
            self.definitions["classic_cross"], style=OverlayStyle(**{**self.definitions["classic_cross"].style.__dict__, "style_id": "creator_test"}), source_type="creator_grid"
        )
        model.style_id = "creator_test"
        self.assertEqual(controller._creator_style_id(model, model.name), "creator_test")


if __name__ == "__main__":
    unittest.main()
