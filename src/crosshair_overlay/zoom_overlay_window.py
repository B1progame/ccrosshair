from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QEvent, QEasingCurve, QPropertyAnimation, QRect, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ZoomOverlayWindow(QWidget):
    HWND_TOPMOST = -1
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOOLWINDOW = 0x00000080
    WDA_NONE = 0x00000000
    WDA_EXCLUDEFROMCAPTURE = 0x00000011

    def __init__(self) -> None:
        super().__init__()
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._long_ptr_type = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
        self._get_window_long_ptr = getattr(self._user32, "GetWindowLongPtrW", self._user32.GetWindowLongW)
        self._set_window_long_ptr = getattr(self._user32, "SetWindowLongPtrW", self._user32.SetWindowLongW)
        self._get_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int]
        self._get_window_long_ptr.restype = self._long_ptr_type
        self._set_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int, self._long_ptr_type]
        self._set_window_long_ptr.restype = self._long_ptr_type
        self._set_window_display_affinity = getattr(self._user32, "SetWindowDisplayAffinity", None)
        if self._set_window_display_affinity is not None:
            self._set_window_display_affinity.argtypes = [wintypes.HWND, wintypes.DWORD]
            self._set_window_display_affinity.restype = wintypes.BOOL
        self._user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        self._image = QLabel(self)
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._animation = QPropertyAnimation(self, b"geometry", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        self.setWindowTitle("Zoom Overlay")
        self.setObjectName("ZoomOverlayWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if hasattr(Qt.WindowType, "WindowTransparentForInput"):
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self._image)
        self.setLayout(layout)
        self.setStyleSheet(
            "background: rgba(15, 23, 35, 235);"
            "border: 2px solid rgba(111, 212, 201, 180);"
            "border-radius: 18px;"
        )

    def show_zoom(self, pixmap: QPixmap, target_rect: QRect, animate: bool, duration_ms: int) -> None:
        if pixmap.isNull():
            return
        self._image.setPixmap(
            pixmap.scaled(
                max(1, target_rect.width() - 20),
                max(1, target_rect.height() - 20),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        if animate:
            self._animation.stop()
            self._animation.setDuration(max(0, duration_ms))
            start_rect = self._scaled_rect(target_rect, 0.72)
            self.setGeometry(start_rect)
            self.show()
            self.raise_()
            self._enforce_native_flags()
            self._animation.setStartValue(start_rect)
            self._animation.setEndValue(target_rect)
            self._animation.start()
        else:
            self.setGeometry(target_rect)
            self.show()
            self.raise_()
            self._enforce_native_flags()

    def hide_zoom(self) -> None:
        self._animation.stop()
        self.hide()

    def _scaled_rect(self, rect: QRect, scale: float) -> QRect:
        width = max(1, int(round(rect.width() * scale)))
        height = max(1, int(round(rect.height() * scale)))
        x = rect.center().x() - (width // 2)
        y = rect.center().y() - (height // 2)
        return QRect(x, y, width, height)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._enforce_native_flags()

    def event(self, event) -> bool:
        if event.type() in {QEvent.Type.WinIdChange, QEvent.Type.ApplicationActivate}:
            self._enforce_native_flags()
        return super().event(event)

    def _enforce_native_flags(self) -> None:
        try:
            hwnd = int(self.winId())
        except Exception:
            return
        if not hwnd:
            return
        ex_style = int(self._get_window_long_ptr(hwnd, self.GWL_EXSTYLE))
        ex_style |= self.WS_EX_TRANSPARENT | self.WS_EX_NOACTIVATE | self.WS_EX_TOOLWINDOW
        self._set_window_long_ptr(hwnd, self.GWL_EXSTYLE, self._long_ptr_type(ex_style))
        if self._set_window_display_affinity is not None:
            try:
                self._set_window_display_affinity(hwnd, self.WDA_EXCLUDEFROMCAPTURE)
            except Exception:
                pass
        self._user32.SetWindowPos(
            hwnd,
            self.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            self.SWP_NOMOVE | self.SWP_NOSIZE | self.SWP_NOACTIVATE | self.SWP_SHOWWINDOW,
        )
