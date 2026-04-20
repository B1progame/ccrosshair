from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QWidget

from .config import OverlayStyle
from .crosshair_widget import CrosshairWidget


class OverlayWindow(QWidget):
    """Transparent, click-through, always-on-top crosshair overlay window."""

    HWND_TOPMOST = -1
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOOLWINDOW = 0x00000080

    def __init__(self, style: OverlayStyle) -> None:
        super().__init__()
        self._style = style
        self._crosshair = CrosshairWidget(style=style, parent=self)
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._long_ptr_type = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
        self._get_window_long_ptr = getattr(self._user32, "GetWindowLongPtrW", self._user32.GetWindowLongW)
        self._set_window_long_ptr = getattr(self._user32, "SetWindowLongPtrW", self._user32.SetWindowLongW)
        self._get_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int]
        self._get_window_long_ptr.restype = self._long_ptr_type
        self._set_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int, self._long_ptr_type]
        self._set_window_long_ptr.restype = self._long_ptr_type
        self._user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        self._apply_window_properties()
        self.center_on_primary_screen()

    def _apply_window_properties(self) -> None:
        self.setObjectName("OverlayWindow")
        self.setWindowTitle("Crosshair Overlay")
        self.setFixedSize(self._crosshair.size())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setStyleSheet("background: transparent; border: none;")

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if hasattr(Qt.WindowType, "WindowTransparentForInput"):
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)

    def set_style(self, style: OverlayStyle) -> None:
        changed = self._crosshair.set_style(style)
        self._style = style
        if not changed:
            return
        self.setFixedSize(self._crosshair.size())
        self._enforce_native_overlay_flags()

    def center_on_primary_screen(self) -> None:
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication instance is required before creating OverlayWindow.")

        screen = app.primaryScreen()
        if screen is None:
            return

        geometry = screen.geometry()
        x = geometry.x() + ((geometry.width() - self.width()) // 2)
        y = geometry.y() + ((geometry.height() - self.height()) // 2)
        self.move(x, y)
        self._enforce_native_overlay_flags()

    def center_on_bounds(self, left: int, top: int, right: int, bottom: int) -> None:
        width = max(1, right - left)
        height = max(1, bottom - top)
        x = left + ((width - self.width()) // 2)
        y = top + ((height - self.height()) // 2)
        self.move(x, y)
        self._enforce_native_overlay_flags()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.center_on_primary_screen()
        self._enforce_native_overlay_flags()

    def event(self, event) -> bool:
        if event.type() in {QEvent.Type.WinIdChange, QEvent.Type.ApplicationActivate}:
            self._enforce_native_overlay_flags()
        return super().event(event)

    def _enforce_native_overlay_flags(self) -> None:
        try:
            hwnd = int(self.winId())
        except Exception:
            return
        if not hwnd:
            return

        ex_style = int(self._get_window_long_ptr(hwnd, self.GWL_EXSTYLE))
        ex_style |= self.WS_EX_LAYERED | self.WS_EX_TRANSPARENT | self.WS_EX_NOACTIVATE | self.WS_EX_TOOLWINDOW
        self._set_window_long_ptr(hwnd, self.GWL_EXSTYLE, self._long_ptr_type(ex_style))
        self._user32.SetWindowPos(
            hwnd,
            self.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            self.SWP_NOMOVE | self.SWP_NOSIZE | self.SWP_NOACTIVATE | self.SWP_SHOWWINDOW,
        )
