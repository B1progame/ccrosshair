from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...crosshairs.models import CrosshairDefinition
from ...overlay_renderer import draw_overlay_style
from ..components import InfoChip, PageHeader, SectionCard


class CrosshairTileButton(QToolButton):
    favorite_clicked = Signal(str)

    def __init__(self, definition: CrosshairDefinition, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.definition = definition
        self._selected = False
        self._active = False
        self._batch_selected = False
        self._favorite_button = QPushButton(self)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(False)
        self.setMinimumSize(176, 186)
        self._favorite_button.setFixedSize(28, 28)
        self._favorite_button.clicked.connect(self._emit_favorite)
        self._refresh_favorite_button()

    def set_state(self, *, selected: bool, active: bool, batch_selected: bool) -> None:
        self._selected = selected
        self._active = active
        self._batch_selected = batch_selected
        self._refresh_favorite_button()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer = self.rect().adjusted(2, 2, -2, -2)
        background = QColor("#182131")
        border = QColor("#2F3B52")
        if self._batch_selected:
            background = QColor("#20324A")
            border = QColor("#69B4FF")
        elif self._selected:
            background = QColor("#243145")
            border = QColor("#6FD4C9")
        if self._active:
            border = QColor("#59D39A")

        painter.setPen(QPen(border, 2))
        painter.setBrush(background)
        painter.drawRoundedRect(outer, 14, 14)

        preview = QRectF(outer.left() + 12, outer.top() + 12, outer.width() - 24, outer.height() - 66)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#101925"))
        painter.drawRoundedRect(preview, 12, 12)
        draw_overlay_style(painter, preview, self.definition.style.scaled(210))

        tag_y = outer.top() + 12
        if self._active:
            self._draw_tag(painter, outer.left() + 12, tag_y, "ACTIVE", QColor("#193B2C"), QColor("#59D39A"))
            tag_y += 26
        if self._batch_selected:
            self._draw_tag(painter, outer.left() + 12, tag_y, "PACK", QColor("#1E3652"), QColor("#69B4FF"))
        elif self._selected:
            self._draw_tag(painter, outer.left() + 12, tag_y, "PREVIEW", QColor("#143C3A"), QColor("#6FD4C9"))

        title_rect = QRectF(outer.left() + 12, outer.bottom() - 46, outer.width() - 24, 22)
        family_rect = QRectF(outer.left() + 12, outer.bottom() - 24, outer.width() - 24, 16)
        painter.setPen(self.palette().text().color())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.definition.display_name)
        painter.setPen(QColor("#94A6C3"))
        painter.drawText(family_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.definition.family)

    def _draw_tag(self, painter: QPainter, x: float, y: float, text: str, bg: QColor, fg: QColor) -> None:
        rect = QRectF(x, y, 58 if len(text) <= 6 else 72, 20)
        painter.setPen(QPen(fg, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(fg)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._favorite_button.move(self.width() - self._favorite_button.width() - 10, 10)

    def sync_definition(self, definition: CrosshairDefinition) -> None:
        self.definition = definition
        self._refresh_favorite_button()
        self.update()

    def _refresh_favorite_button(self) -> None:
        self._favorite_button.setText("♥" if self.definition.is_favorite else "♡")
        self._favorite_button.setObjectName("PrimaryButton" if self.definition.is_favorite else "GhostButton")
        self._favorite_button.setToolTip("Remove Favorite" if self.definition.is_favorite else "Add Favorite")
        self._favorite_button.style().unpolish(self._favorite_button)
        self._favorite_button.style().polish(self._favorite_button)
        self._favorite_button.raise_()

    def _emit_favorite(self) -> None:
        self.favorite_clicked.emit(self.definition.style_id)


class CrosshairsPage(QWidget):
    style_selected = Signal(str)
    detail_requested = Signal(str)
    favorite_toggled = Signal(str)
    selected_size_changed = Signal(int)
    import_pack_requested = Signal(str)
    export_pack_requested = Signal(str)
    export_selection_requested = Signal(list, str)

    def __init__(
        self,
        definitions: "OrderedDict[str, CrosshairDefinition]",
        current_style_id: str,
        selected_size_percent: int,
    ) -> None:
        super().__init__()
        self._definitions = definitions
        self._active_style_id = current_style_id
        self._selected_style_id = current_style_id
        self._multi_select_mode = False
        self._selected_batch_ids: set[str] = set()
        self._search = QLineEdit(self)
        self._folder_buttons: dict[str, QPushButton] = {}
        self._folder_id = "all"
        self._gallery_grid = QGridLayout()
        self._gallery_widget = QWidget(self)
        self._gallery_scroll = QScrollArea(self)
        self._folder_scroll = QScrollArea(self)
        self._folder_container = QWidget(self)
        self._folder_container_layout = QHBoxLayout()
        self._selection_summary = QLabel("-", self)
        self._active_summary = QLabel("-", self)
        self._size_value = QLabel("", self)
        self._size_slider = QSlider(self)
        self._use_button = QPushButton("Use This", self)
        self._multi_button = QPushButton("Select Multiple", self)
        self._cancel_multi_button = QPushButton("Cancel Selection", self)
        self._export_pack_button = QPushButton("Export Pack", self)
        self._import_button = QPushButton("Import", self)
        self._export_button = QPushButton("Export This", self)
        self._open_detail = QPushButton("Open Detail", self)
        self._favorite_button = QPushButton("Favorite", self)
        self._tile_buttons: dict[str, CrosshairTileButton] = {}
        self._build_ui()
        self._populate_folders()
        self._populate_gallery()
        self.set_selected_size(selected_size_percent)
        self._wire_signals()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(
            PageHeader(
                "Crosshairs",
                "Browse built-ins, imports, and creator styles with a clearer separation between preview, active use, and pack selection.",
                eyebrow="Library",
                parent=self,
            )
        )

        toolbar = QFrame(self)
        toolbar.setObjectName("HeroCard")
        toolbar_layout = QVBoxLayout()
        toolbar_layout.setContentsMargins(18, 18, 18, 18)
        toolbar_layout.setSpacing(12)

        top_row = QHBoxLayout()
        self._search.setPlaceholderText("Search by name, family, source, or tag")
        top_row.addWidget(self._search, 1)
        self._use_button.setObjectName("PrimaryButton")
        self._export_pack_button.setObjectName("PrimaryButton")
        self._cancel_multi_button.setObjectName("GhostButton")
        top_row.addWidget(self._use_button)
        top_row.addWidget(self._open_detail)
        top_row.addWidget(self._multi_button)
        top_row.addWidget(self._cancel_multi_button)
        top_row.addWidget(self._export_pack_button)
        top_row.addWidget(self._import_button)
        toolbar_layout.addLayout(top_row)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(InfoChip("Library Folders", accent=True, parent=self))
        self._folder_container_layout.setContentsMargins(0, 0, 0, 0)
        self._folder_container_layout.setSpacing(8)
        self._folder_container.setLayout(self._folder_container_layout)
        self._folder_scroll.setWidgetResizable(True)
        self._folder_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._folder_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._folder_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._folder_scroll.setWidget(self._folder_container)
        folder_row.addWidget(self._folder_scroll, 1)
        toolbar_layout.addLayout(folder_row)
        toolbar.setLayout(toolbar_layout)
        root.addWidget(toolbar)

        content = QHBoxLayout()
        content.setSpacing(16)

        gallery_card = SectionCard(
            "Crosshair Browser",
            "Single click previews a style. Use the strong action button to make it live. Multi-select mode builds packs.",
            parent=self,
        )
        self._gallery_grid.setContentsMargins(0, 0, 0, 0)
        self._gallery_grid.setHorizontalSpacing(12)
        self._gallery_grid.setVerticalSpacing(12)
        self._gallery_widget.setLayout(self._gallery_grid)
        self._gallery_scroll.setWidgetResizable(True)
        self._gallery_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._gallery_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._gallery_scroll.setWidget(self._gallery_widget)
        gallery_card.body.addWidget(self._gallery_scroll, 1)
        content.addWidget(gallery_card, 4)

        side = QVBoxLayout()
        side.setSpacing(16)

        summary_card = SectionCard("Selection", "", object_name="SubtleCard", parent=self)
        summary_card.body.addWidget(QLabel("Previewed", self))
        summary_card.body.addWidget(self._selection_summary)
        summary_card.body.addWidget(QLabel("Active In Overlay", self))
        summary_card.body.addWidget(self._active_summary)
        summary_card.body.addWidget(QLabel("Current Size", self))
        self._size_slider.setOrientation(Qt.Orientation.Horizontal)
        self._size_slider.setMinimum(50)
        self._size_slider.setMaximum(200)
        self._size_slider.setSingleStep(5)
        summary_card.body.addWidget(self._size_slider)
        summary_card.body.addWidget(self._size_value)
        side.addWidget(summary_card)

        actions_card = SectionCard("Actions", "", parent=self)
        actions_card.body.addWidget(self._favorite_button)
        actions_card.body.addWidget(self._export_button)
        actions_card.body.addStretch(1)
        side.addWidget(actions_card)
        side.addStretch(1)

        side_wrap = QWidget(self)
        side_wrap.setLayout(side)
        content.addWidget(side_wrap, 2)

        root.addLayout(content, 1)
        self.setLayout(root)

    def _wire_signals(self) -> None:
        self._search.textChanged.connect(lambda _text: self._populate_gallery())
        self._use_button.clicked.connect(self._use_selected)
        self._open_detail.clicked.connect(self._on_open_detail)
        self._multi_button.clicked.connect(self._enter_multi_select)
        self._cancel_multi_button.clicked.connect(self._cancel_multi_select)
        self._export_pack_button.clicked.connect(self._export_selected_pack)
        self._import_button.clicked.connect(self._on_import_clicked)
        self._export_button.clicked.connect(self._on_export_clicked)
        self._favorite_button.clicked.connect(self._on_toggle_favorite)
        self._size_slider.valueChanged.connect(self._on_size_changed)

    def _folder_entries(self) -> list[tuple[str, str]]:
        entries = [("all", "All"), ("builtin", "Built-in"), ("favorites", "Favorites")]
        if any(item.source_type != "builtin" for item in self._definitions.values()):
            entries.append(("imports", "Imports"))
            entries.append(("creator", "Creator"))
            entries.append(("custom", "Custom"))
        families = sorted({item.family for item in self._definitions.values() if item.source_type == "builtin"})
        entries.extend((f"family:{family}", family) for family in families)
        return entries

    def _populate_folders(self) -> None:
        self._folder_buttons.clear()
        while self._folder_container_layout.count() > 0:
            item = self._folder_container_layout.takeAt(0)
            if item is not None and item.widget() is not None:
                item.widget().deleteLater()

        for folder_id, label in self._folder_entries():
            button = QPushButton(label, self)
            button.setCheckable(True)
            button.setChecked(folder_id == self._folder_id)
            if folder_id == self._folder_id:
                button.setObjectName("PrimaryButton")
            button.clicked.connect(lambda _checked=False, fid=folder_id: self._select_folder(fid))
            self._folder_buttons[folder_id] = button
            self._folder_container_layout.addWidget(button)
        self._folder_container_layout.addStretch(1)

    def _select_folder(self, folder_id: str) -> None:
        self._folder_id = folder_id
        for fid, button in self._folder_buttons.items():
            button.setChecked(fid == folder_id)
            button.setObjectName("PrimaryButton" if fid == folder_id else "")
            button.style().polish(button)
        self._populate_gallery()

    def _matches_folder(self, item: CrosshairDefinition) -> bool:
        if self._folder_id == "all":
            return True
        if self._folder_id == "builtin":
            return item.source_type == "builtin"
        if self._folder_id == "favorites":
            return item.is_favorite
        if self._folder_id == "imports":
            return item.source_type in {"imported_pack", "plugin_pack", "legacy_pack"}
        if self._folder_id == "creator":
            return item.source_type == "creator_grid"
        if self._folder_id == "custom":
            return item.source_type == "custom"
        if self._folder_id.startswith("family:"):
            return item.family == self._folder_id.split(":", 1)[1]
        return True

    def _filtered_items(self) -> list[CrosshairDefinition]:
        query = self._search.text().strip().lower()
        items: list[CrosshairDefinition] = []
        for item in self._definitions.values():
            if not self._matches_folder(item):
                continue
            if query:
                haystack = " ".join(
                    [
                        item.display_name,
                        item.family,
                        item.description,
                        item.source_type,
                        " ".join(item.tags),
                    ]
                ).lower()
                if query not in haystack:
                    continue
            items.append(item)
        return items

    def _populate_gallery(self) -> None:
        while self._gallery_grid.count() > 0:
            item = self._gallery_grid.takeAt(0)
            if item is not None and item.widget() is not None:
                item.widget().deleteLater()

        self._tile_buttons.clear()
        filtered = self._filtered_items()
        if not filtered:
            empty = QLabel("Nothing matches this view yet. Try another folder or import a pack.", self)
            empty.setObjectName("Muted")
            empty.setWordWrap(True)
            self._gallery_grid.addWidget(empty, 0, 0)
            self._refresh_side_panel()
            return

        if self._selected_style_id not in {item.style_id for item in filtered}:
            self._selected_style_id = filtered[0].style_id

        tile_width = 186
        viewport_width = max(tile_width, self._gallery_scroll.viewport().width())
        columns = max(1, viewport_width // tile_width)
        for index, definition in enumerate(filtered):
            tile = CrosshairTileButton(definition, self)
            tile.clicked.connect(lambda _checked=False, sid=definition.style_id: self._on_tile_clicked(sid))
            tile.favorite_clicked.connect(self.favorite_toggled.emit)
            self._tile_buttons[definition.style_id] = tile
            self._gallery_grid.addWidget(tile, index // columns, index % columns)

        self._refresh_tile_states()
        self._refresh_side_panel()

    def refresh_definitions(self, definitions: "OrderedDict[str, CrosshairDefinition]", selected_style_id: str) -> None:
        self._definitions = definitions
        self._active_style_id = selected_style_id
        if selected_style_id in definitions:
            self._selected_style_id = selected_style_id
        self._selected_batch_ids = {style_id for style_id in self._selected_batch_ids if style_id in definitions}
        self._populate_folders()
        self._populate_gallery()

    def set_selected_style(self, style_id: str) -> None:
        if style_id in self._definitions:
            self._active_style_id = style_id
            if not self._multi_select_mode:
                self._selected_style_id = style_id
        self._refresh_tile_states()
        self._refresh_side_panel()

    def set_selected_size(self, value: int) -> None:
        self._size_slider.setValue(max(50, min(200, value)))
        self._size_value.setText(f"{self._size_slider.value()}%")

    def _on_tile_clicked(self, style_id: str) -> None:
        if style_id not in self._definitions:
            return
        if self._multi_select_mode:
            if style_id in self._selected_batch_ids:
                self._selected_batch_ids.remove(style_id)
            else:
                self._selected_batch_ids.add(style_id)
            self._selected_style_id = style_id
        else:
            self._selected_style_id = style_id
        self._refresh_tile_states()
        self._refresh_side_panel()

    def _refresh_tile_states(self) -> None:
        for style_id, tile in self._tile_buttons.items():
            if style_id in self._definitions:
                tile.sync_definition(self._definitions[style_id])
            tile.set_state(
                selected=style_id == self._selected_style_id,
                active=style_id == self._active_style_id,
                batch_selected=style_id in self._selected_batch_ids,
            )

    def _refresh_side_panel(self) -> None:
        selected = self._definitions.get(self._selected_style_id)
        active = self._definitions.get(self._active_style_id)

        if selected is None:
            self._selection_summary.setText("No crosshair selected")
        else:
            self._selection_summary.setText(
                f"{selected.display_name}\nFamily: {selected.family}\nSource: {selected.source_type}"
            )
            self._favorite_button.setText("♥ Remove Favorite" if selected.is_favorite else "♡ Add Favorite")

        if active is None:
            self._active_summary.setText("No active crosshair")
        else:
            self._active_summary.setText(f"{active.display_name}\nLive in overlay")

        self._use_button.setEnabled(selected is not None and selected.style_id != self._active_style_id and not self._multi_select_mode)
        self._open_detail.setEnabled(selected is not None and not self._multi_select_mode)
        self._favorite_button.setEnabled(selected is not None and not self._multi_select_mode)
        self._export_button.setEnabled(selected is not None and not self._multi_select_mode)
        self._cancel_multi_button.setVisible(self._multi_select_mode)
        self._export_pack_button.setVisible(self._multi_select_mode)
        self._export_pack_button.setEnabled(len(self._selected_batch_ids) > 0)
        self._multi_button.setText("Multi-Select On" if self._multi_select_mode else "Select Multiple")

    def _use_selected(self) -> None:
        if self._selected_style_id and self._selected_style_id in self._definitions:
            self._active_style_id = self._selected_style_id
            self.style_selected.emit(self._selected_style_id)
            self._refresh_tile_states()
            self._refresh_side_panel()

    def _enter_multi_select(self) -> None:
        self._multi_select_mode = True
        self._selected_batch_ids = set()
        self._refresh_side_panel()
        self._refresh_tile_states()

    def _cancel_multi_select(self) -> None:
        self._multi_select_mode = False
        self._selected_batch_ids.clear()
        self._refresh_side_panel()
        self._refresh_tile_states()

    def _export_selected_pack(self) -> None:
        if not self._selected_batch_ids:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Crosshair Pack",
            str(Path.home() / "crosshair_pack.xpack"),
            "Crosshair Pack (*.xpack)",
        )
        if not path:
            return
        if not path.lower().endswith(".xpack"):
            path = f"{path}.xpack"
        self.export_selection_requested.emit(sorted(self._selected_batch_ids), path)

    def _on_size_changed(self, value: int) -> None:
        self._size_value.setText(f"{value}%")
        self.selected_size_changed.emit(value)

    def _on_import_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Crosshair or Pack",
            str(Path.home()),
            "Crosshair Files (*.xhair *.xpack *.chpack *.chgrid)",
        )
        if path:
            self.import_pack_requested.emit(path)

    def _on_export_clicked(self) -> None:
        current = self._selected_style_id
        if not current or current not in self._definitions:
            return
        style_name = self._definitions[current].display_name.strip().replace(" ", "_").lower()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Crosshair",
            str(Path.home() / f"{style_name}.xhair"),
            "Crosshair Definition (*.xhair)",
        )
        if path:
            if not path.lower().endswith(".xhair"):
                path = f"{path}.xhair"
            self.export_pack_requested.emit(path)

    def _on_open_detail(self, *_args) -> None:
        if self._selected_style_id:
            self.detail_requested.emit(self._selected_style_id)

    def _on_toggle_favorite(self) -> None:
        if self._selected_style_id:
            self.favorite_toggled.emit(self._selected_style_id)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._populate_gallery()
