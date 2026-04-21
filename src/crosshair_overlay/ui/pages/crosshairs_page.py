from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QEvent, QEasingCurve, QPropertyAnimation, QRect, QTimer, Qt, Signal
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
    QVBoxLayout,
    QWidget,
)

from ...crosshairs.models import CrosshairDefinition
from ...widgets import CrosshairCardButton
from ..components import InfoChip, PageHeader, SectionCard


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
        self._selection_drawer = QFrame(self)
        self._drawer_toggle_button = QPushButton("\u25c0", self._selection_drawer)
        self._drawer_animation = QPropertyAnimation(self._selection_drawer, b"geometry", self)
        self._drawer_animation.setDuration(220)
        self._drawer_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._drawer_animation.finished.connect(self._on_drawer_animation_finished)
        self._tile_buttons: dict[str, CrosshairCardButton] = {}
        self._pending_tiles: list[tuple[int, CrosshairDefinition, int]] = []
        self._tile_build_timer = QTimer(self)
        self._tile_build_timer.setInterval(0)
        self._tile_build_timer.timeout.connect(self._build_next_tile_batch)
        self._gallery_rebuild_timer = QTimer(self)
        self._gallery_rebuild_timer.setSingleShot(True)
        self._gallery_rebuild_timer.setInterval(90)
        self._gallery_rebuild_timer.timeout.connect(self._populate_gallery)
        self._current_columns = 0
        self._drawer_visible = False
        self._drawer_width = 360
        self._quick_view = "all"
        self._build_ui()
        self._gallery_scroll.viewport().installEventFilter(self)
        self._populate_folders()
        self._populate_gallery()
        self.set_selected_size(selected_size_percent)
        self._wire_signals()

    def _build_ui(self) -> None:
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget(self)
        root = QVBoxLayout(content_widget)
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
        top_row.setSpacing(8)
        self._search.setPlaceholderText("Search by name, family, source, or tag")
        top_row.addWidget(self._search, 1)
        self._export_pack_button.setObjectName("PrimaryButton")
        self._cancel_multi_button.setObjectName("GhostButton")
        top_row.addWidget(self._multi_button)
        top_row.addWidget(self._import_button)
        top_row.addStretch(1)
        toolbar_layout.addLayout(top_row)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        mode_row.addWidget(self._cancel_multi_button)
        mode_row.addWidget(self._export_pack_button)
        mode_row.addStretch(1)
        toolbar_layout.addLayout(mode_row)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(InfoChip("Library Folders", accent=True, parent=self))
        self._folder_container_layout.setContentsMargins(0, 0, 0, 0)
        self._folder_container_layout.setSpacing(8)
        self._folder_container.setLayout(self._folder_container_layout)
        self._folder_scroll.setWidgetResizable(True)
        self._folder_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._folder_scroll.setObjectName("FolderScrollArea")
        self._folder_scroll.viewport().setObjectName("FolderScrollViewport")
        self._folder_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._folder_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._folder_scroll.setWidget(self._folder_container)
        folder_row.addWidget(self._folder_scroll, 1)
        toolbar_layout.addLayout(folder_row)
        toolbar.setLayout(toolbar_layout)
        root.addWidget(toolbar)

        content = QVBoxLayout()
        content.setSpacing(14)

        gallery_card = SectionCard(
            "Crosshair Browser",
            "Single click previews a style. Use the strong action button to make it live. Multi-select mode builds packs.",
            parent=self,
        )
        self._gallery_grid.setContentsMargins(8, 8, 8, 8)
        self._gallery_grid.setHorizontalSpacing(12)
        self._gallery_grid.setVerticalSpacing(12)
        self._gallery_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._gallery_widget.setLayout(self._gallery_grid)
        self._gallery_scroll.setWidgetResizable(True)
        self._gallery_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._gallery_scroll.setObjectName("GalleryScrollArea")
        self._gallery_scroll.viewport().setObjectName("GalleryScrollViewport")
        self._gallery_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._gallery_scroll.setWidget(self._gallery_widget)
        gallery_card.body.addWidget(self._gallery_scroll, 1)
        content.addWidget(gallery_card, 1)

        root.addLayout(content, 1)
        scroll.setWidget(content_widget)
        outer.addWidget(scroll)
        self.setLayout(outer)
        self._build_selection_drawer()

    def _build_selection_drawer(self) -> None:
        self._selection_drawer.setObjectName("Card")
        self._selection_drawer.setFrameShape(QFrame.Shape.NoFrame)
        self._use_button.setObjectName("PrimaryButton")
        self._open_detail.setObjectName("GhostButton")
        self._favorite_button.setObjectName("GhostButton")
        self._export_button.setObjectName("GhostButton")
        drawer_layout = QVBoxLayout()
        drawer_layout.setContentsMargins(14, 14, 14, 14)
        drawer_layout.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel("Selection", self._selection_drawer)
        title.setObjectName("CardTitle")
        top.addWidget(title)
        top.addStretch(1)
        self._drawer_toggle_button.setObjectName("DrawerCloseButton")
        self._drawer_toggle_button.setFixedSize(32, 32)
        self._drawer_toggle_button.setText("X")
        self._drawer_toggle_button.setToolTip("Hide sidebar")
        top.addWidget(self._drawer_toggle_button)
        drawer_layout.addLayout(top)

        self._selection_summary.setWordWrap(True)
        self._active_summary.setWordWrap(True)
        drawer_layout.addWidget(QLabel("Previewed", self._selection_drawer))
        drawer_layout.addWidget(self._selection_summary)
        drawer_layout.addWidget(QLabel("Active In Overlay", self._selection_drawer))
        drawer_layout.addWidget(self._active_summary)
        drawer_layout.addWidget(QLabel("Current Size", self._selection_drawer))
        self._size_slider.setOrientation(Qt.Orientation.Horizontal)
        self._size_slider.setMinimum(50)
        self._size_slider.setMaximum(200)
        self._size_slider.setSingleStep(5)
        drawer_layout.addWidget(self._size_slider)
        drawer_layout.addWidget(self._size_value)

        drawer_layout.addSpacing(4)
        drawer_layout.addWidget(self._favorite_button)
        drawer_layout.addWidget(self._export_button)
        drawer_layout.addWidget(self._open_detail)
        drawer_layout.addWidget(self._use_button)
        drawer_layout.addStretch(1)

        self._selection_drawer.setLayout(drawer_layout)
        self._selection_drawer.hide()
        self._selection_drawer.raise_()

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
        self._drawer_toggle_button.clicked.connect(lambda: self._hide_drawer(animated=True))

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
        self._folder_container_layout.setContentsMargins(8, 6, 8, 6)
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
            button.style().unpolish(button)
            button.style().polish(button)
        self._populate_gallery()

    def _matches_folder(self, item: CrosshairDefinition) -> bool:
        if self._quick_view == "my":
            if item.is_favorite:
                return True
            if item.source_type in {"custom", "creator_grid", "imported_pack", "plugin_pack", "legacy_pack"}:
                return True
            return False
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
        self._tile_build_timer.stop()
        self._pending_tiles.clear()
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

        min_tile_width = 182
        spacing = max(8, self._gallery_grid.horizontalSpacing())
        viewport_width = max(min_tile_width, self._gallery_scroll.viewport().width() - 4)
        columns = max(1, (viewport_width + spacing) // (min_tile_width + spacing))
        tile_width = min_tile_width
        self._current_columns = columns
        self._pending_tiles = [(index, definition, columns, tile_width) for index, definition in enumerate(filtered)]
        self._build_next_tile_batch()
        self._refresh_side_panel()

    def _build_next_tile_batch(self) -> None:
        if not self._pending_tiles:
            self._tile_build_timer.stop()
            self._refresh_tile_states()
            return
        batch_size = 18
        for _ in range(min(batch_size, len(self._pending_tiles))):
            index, definition, columns, tile_width = self._pending_tiles.pop(0)
            tile = CrosshairCardButton(definition, parent=self)
            tile.setFixedSize(tile_width, CrosshairCardButton.CARD_HEIGHT)
            tile.clicked.connect(lambda _checked=False, sid=definition.style_id: self._on_tile_clicked(sid))
            tile.favorite_clicked.connect(self.favorite_toggled.emit)
            self._tile_buttons[definition.style_id] = tile
            row = index // columns
            col = index % columns
            self._gallery_grid.setRowMinimumHeight(row, CrosshairCardButton.CARD_HEIGHT)
            self._gallery_grid.addWidget(tile, row, col)
        self._refresh_tile_states()
        if self._pending_tiles:
            self._tile_build_timer.start()

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

    def set_quick_view(self, view: str) -> None:
        view = (view or "all").strip().lower()
        if view not in {"all", "my"}:
            view = "all"
        if self._quick_view == view:
            return
        self._quick_view = view
        if view == "my" and self._folder_id == "builtin":
            self._folder_id = "favorites"
            self._populate_folders()
        self._populate_gallery()

    def _drawer_target_rect(self, visible: bool | None = None) -> QRect:
        if visible is None:
            visible = self._drawer_visible
        width = self._drawer_width
        height = max(260, self.height() - 190)
        y = 166
        x_visible = self.width() - width - 18
        x_hidden = self.width() + 8
        return QRect(x_visible if visible else x_hidden, y, width, height)

    def _show_drawer(self, animated: bool = True) -> None:
        if self._drawer_visible and self._selection_drawer.isVisible():
            return
        self._drawer_visible = True
        self._selection_drawer.show()
        self._selection_drawer.raise_()
        if not animated:
            self._selection_drawer.setGeometry(self._drawer_target_rect(True))
            return
        self._drawer_animation.stop()
        self._drawer_animation.setStartValue(self._drawer_target_rect(False))
        self._drawer_animation.setEndValue(self._drawer_target_rect(True))
        self._drawer_animation.start()

    def _hide_drawer(self, animated: bool = True) -> None:
        if not self._drawer_visible:
            return
        self._drawer_visible = False
        if not animated:
            self._selection_drawer.hide()
            return
        self._drawer_animation.stop()
        self._drawer_animation.setStartValue(self._selection_drawer.geometry())
        self._drawer_animation.setEndValue(self._drawer_target_rect(False))
        self._drawer_animation.start()

    def _on_drawer_animation_finished(self) -> None:
        if not self._drawer_visible:
            self._selection_drawer.hide()

    def _on_tile_clicked(self, style_id: str) -> None:
        if style_id not in self._definitions:
            return
        self._show_drawer(animated=True)
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
                style_id == self._selected_style_id,
                style_id == self._active_style_id,
                style_id in self._selected_batch_ids,
            )

    def _refresh_side_panel(self) -> None:
        selected = self._definitions.get(self._selected_style_id)
        active = self._definitions.get(self._active_style_id)

        if selected is None:
            self._selection_summary.setText("No crosshair selected")
            self._hide_drawer(animated=True)
        else:
            self._selection_summary.setText(
                f"{selected.display_name}\nFamily: {selected.family}\nSource: {selected.source_type}"
            )
            self._favorite_button.setText("\u2665 Remove Favorite" if selected.is_favorite else "\u2661 Add Favorite")

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

    def eventFilter(self, watched, event):  # noqa: N802
        if watched == self._gallery_scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._gallery_rebuild_timer.start()
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._gallery_rebuild_timer.start()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._drawer_visible:
            self._selection_drawer.setGeometry(self._drawer_target_rect(True))
        elif self._selection_drawer.isVisible():
            self._selection_drawer.setGeometry(self._drawer_target_rect(False))
        self._gallery_rebuild_timer.start()

