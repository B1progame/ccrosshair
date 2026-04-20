from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .history import GridHistory


class GridEditorWidget(QWidget):
    state_changed = Signal()
    undo_redo_changed = Signal(bool, bool)
    line_anchor_changed = Signal(bool)
    hovered_cell_changed = Signal(str)

    def __init__(self, grid_size: int = 32, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._grid_size = grid_size
        self._cells: set[tuple[int, int]] = set()
        self._history = GridHistory()
        self._history.set_initial(self._cells)
        self._draw_color = QColor("#FFFFFF")
        self._tool = "draw"
        self._brush_size = 1
        self._show_grid = True
        self._mirror_x = False
        self._mirror_y = False
        self._dragging = False
        self._last_applied: set[tuple[int, int]] = set()
        self._grid_rect = QRectF()
        self._zoom_percent = 100
        self._hover_cell: tuple[int, int] | None = None
        self._line_anchor: tuple[int, int] | None = None
        self.setMinimumSize(520, 520)
        self.setMouseTracking(True)

    def set_tool(self, tool: str) -> None:
        if tool not in {"draw", "erase", "line"}:
            return
        self._tool = tool
        if tool != "line" and self._line_anchor is not None:
            self._line_anchor = None
            self.line_anchor_changed.emit(False)
        self.update()

    def set_brush_size(self, size: int) -> None:
        self._brush_size = max(1, min(8, int(size)))

    def set_color_hex(self, color_hex: str) -> None:
        color = QColor(color_hex)
        if color.isValid():
            self._draw_color = color
            self.update()

    def set_show_grid(self, show: bool) -> None:
        self._show_grid = show
        self.update()

    def set_mirror(self, mirror_x: bool, mirror_y: bool) -> None:
        self._mirror_x = mirror_x
        self._mirror_y = mirror_y

    def set_grid_size(self, grid_size: int, preserve: bool = False) -> None:
        bounded = max(16, min(64, int(grid_size)))
        if bounded == self._grid_size:
            return
        existing = set(self._cells)
        old_size = self._grid_size
        self._grid_size = bounded
        if preserve:
            self._cells = self._scaled_cells(existing, old_size, bounded)
        else:
            self._cells.clear()
        self._line_anchor = None
        self._history.set_initial(self._cells)
        self._emit_history()
        self.state_changed.emit()
        self.update()

    def set_zoom_percent(self, zoom_percent: int) -> None:
        self._zoom_percent = max(60, min(240, int(zoom_percent)))
        self.update()

    def clear_canvas(self) -> None:
        self._cells.clear()
        if self._history.commit(self._cells):
            self._emit_history()
        self.state_changed.emit()
        self.update()

    def set_cells(self, cells: set[tuple[int, int]], reset_history: bool = False) -> None:
        self._cells = set(cells)
        if reset_history:
            self._history.set_initial(self._cells)
            self._emit_history()
        self.state_changed.emit()
        self.update()

    def cells(self) -> set[tuple[int, int]]:
        return set(self._cells)

    def grid_size(self) -> int:
        return self._grid_size

    def line_pending(self) -> bool:
        return self._line_anchor is not None

    def undo(self) -> None:
        state = self._history.undo()
        if state is None:
            return
        self._cells = state
        self._line_anchor = None
        self.line_anchor_changed.emit(False)
        self._emit_history()
        self.state_changed.emit()
        self.update()

    def redo(self) -> None:
        state = self._history.redo()
        if state is None:
            return
        self._cells = state
        self._line_anchor = None
        self.line_anchor_changed.emit(False)
        self._emit_history()
        self.state_changed.emit()
        self.update()

    def can_undo(self) -> bool:
        return self._history.can_undo()

    def can_redo(self) -> bool:
        return self._history.can_redo()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        bg = self.palette().window().color()
        panel = self.palette().base().color()
        grid_line = self.palette().mid().color()
        guide = self.palette().highlight().color()
        preview = QColor(self._draw_color)
        preview.setAlpha(120)
        guide.setAlpha(145)

        painter.fillRect(self.rect(), bg)

        base_side = min(self.width(), self.height()) - 34
        scaled_side = int(base_side * (self._zoom_percent / 100.0))
        side = max(180, min(base_side, scaled_side))
        left = (self.width() - side) // 2
        top = (self.height() - side) // 2
        self._grid_rect = QRectF(left, top, side, side)
        painter.fillRect(self._grid_rect, panel)

        cell_size = self._grid_rect.width() / self._grid_size
        fill = QColor(self._draw_color)
        for x, y in self._cells:
            painter.fillRect(self._cell_rect(x, y, cell_size), fill)

        if self._tool == "line" and self._line_anchor is not None and self._hover_cell is not None:
            for x, y in self._line_cells(self._line_anchor, self._hover_cell):
                painter.fillRect(self._cell_rect(x, y, cell_size), preview)

        if self._show_grid:
            pen = QPen(grid_line, 1)
            painter.setPen(pen)
            for i in range(self._grid_size + 1):
                offset = i * cell_size
                painter.drawLine(
                    self._grid_rect.left() + offset,
                    self._grid_rect.top(),
                    self._grid_rect.left() + offset,
                    self._grid_rect.bottom(),
                )
                painter.drawLine(
                    self._grid_rect.left(),
                    self._grid_rect.top() + offset,
                    self._grid_rect.right(),
                    self._grid_rect.top() + offset,
                )

        center_pen = QPen(guide, 1.5)
        painter.setPen(center_pen)
        cx = self._grid_rect.left() + ((self._grid_size / 2.0) * cell_size)
        cy = self._grid_rect.top() + ((self._grid_size / 2.0) * cell_size)
        painter.drawLine(cx, self._grid_rect.top(), cx, self._grid_rect.bottom())
        painter.drawLine(self._grid_rect.left(), cy, self._grid_rect.right(), cy)

        if self._hover_cell is not None:
            hover_pen = QPen(self.palette().highlight().color(), 2)
            painter.setPen(hover_pen)
            painter.drawRect(self._cell_rect(self._hover_cell[0], self._hover_cell[1], cell_size))

        if self._line_anchor is not None:
            anchor_pen = QPen(self.palette().highlight().color(), 2)
            painter.setPen(anchor_pen)
            painter.drawRect(self._cell_rect(self._line_anchor[0], self._line_anchor[1], cell_size))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        cell = self._pos_to_cell(event.position().x(), event.position().y())
        if cell is None:
            return
        if self._tool == "line":
            self._handle_line_click(cell)
            return
        self._dragging = True
        self._last_applied.clear()
        self._apply_brush(cell)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        cell = self._pos_to_cell(event.position().x(), event.position().y())
        if cell != self._hover_cell:
            self._hover_cell = cell
            self.hovered_cell_changed.emit(f"{cell[0]}, {cell[1]}" if cell is not None else "-")
            self.update()
        if not self._dragging or cell is None:
            return
        self._apply_brush(cell)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or not self._dragging:
            return
        self._dragging = False
        self._last_applied.clear()
        self.state_changed.emit()

    def leaveEvent(self, event) -> None:  # noqa: N802
        del event
        self._hover_cell = None
        self.hovered_cell_changed.emit("-")
        self.update()

    def _handle_line_click(self, cell: tuple[int, int]) -> None:
        if self._line_anchor is None:
            self._line_anchor = cell
            self.line_anchor_changed.emit(True)
            self.update()
            return
        points = self._line_cells(self._line_anchor, cell)
        self._cells.update(points)
        if self._history.commit(self._cells):
            self._emit_history()
        self._line_anchor = None
        self.line_anchor_changed.emit(False)
        self.state_changed.emit()
        self.update()

    def _apply_brush(self, cell: tuple[int, int]) -> None:
        affected = self._brush_cells(cell[0], cell[1])
        if affected == self._last_applied:
            return
        self._last_applied = set(affected)
        if self._tool == "erase":
            self._cells.difference_update(affected)
        else:
            self._cells.update(affected)
        if self._history.commit(self._cells):
            self._emit_history()
        self.state_changed.emit()
        self.update()

    def _pos_to_cell(self, px: float, py: float) -> tuple[int, int] | None:
        if not self._grid_rect.contains(px, py):
            return None
        cell_size = self._grid_rect.width() / self._grid_size
        x = int((px - self._grid_rect.left()) // cell_size)
        y = int((py - self._grid_rect.top()) // cell_size)
        x = max(0, min(self._grid_size - 1, x))
        y = max(0, min(self._grid_size - 1, y))
        return x, y

    def _brush_cells(self, cx: int, cy: int) -> set[tuple[int, int]]:
        points: set[tuple[int, int]] = set()
        start = -(self._brush_size // 2)
        end = start + self._brush_size
        for ox in range(start, end):
            for oy in range(start, end):
                self._add_point(points, cx + ox, cy + oy)
        return points

    def _line_cells(self, start: tuple[int, int], end: tuple[int, int]) -> set[tuple[int, int]]:
        points: set[tuple[int, int]] = set()
        x1, y1 = start
        x2, y2 = end
        dx = abs(x2 - x1)
        dy = -abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx + dy
        while True:
            brush_points = self._brush_cells(x1, y1)
            points.update(brush_points)
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x1 += sx
            if e2 <= dx:
                err += dx
                y1 += sy
        return points

    def _add_point(self, points: set[tuple[int, int]], x: int, y: int) -> None:
        if not (0 <= x < self._grid_size and 0 <= y < self._grid_size):
            return
        points.add((x, y))
        if self._mirror_x:
            mx = (self._grid_size - 1) - x
            points.add((mx, y))
        if self._mirror_y:
            my = (self._grid_size - 1) - y
            points.add((x, my))
        if self._mirror_x and self._mirror_y:
            mx = (self._grid_size - 1) - x
            my = (self._grid_size - 1) - y
            points.add((mx, my))

    def _cell_rect(self, x: int, y: int, cell_size: float) -> QRectF:
        return QRectF(
            self._grid_rect.left() + (x * cell_size),
            self._grid_rect.top() + (y * cell_size),
            cell_size,
            cell_size,
        )

    def _scaled_cells(self, cells: set[tuple[int, int]], old_grid_size: int, target_grid_size: int) -> set[tuple[int, int]]:
        if not cells:
            return set()
        old_size = max(1, old_grid_size)
        scaled: set[tuple[int, int]] = set()
        for x, y in cells:
            nx = int(round((x / max(1, old_size - 1)) * max(1, target_grid_size - 1)))
            ny = int(round((y / max(1, old_size - 1)) * max(1, target_grid_size - 1)))
            scaled.add((max(0, min(target_grid_size - 1, nx)), max(0, min(target_grid_size - 1, ny))))
        return scaled

    def _emit_history(self) -> None:
        self.undo_redo_changed.emit(self._history.can_undo(), self._history.can_redo())
