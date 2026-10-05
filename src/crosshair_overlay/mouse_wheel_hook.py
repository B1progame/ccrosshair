from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal


WH_MOUSE_LL = 14
WM_MOUSEWHEEL = 0x020A
HC_ACTION = 0


class _Point(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _MouseHookData(ctypes.Structure):
    _fields_ = [("pt", _Point), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


_LowLevelMouseProc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class GlobalMouseWheelHook(QObject):
    """Observe global wheel input only while active; optionally consume it."""
    wheel_delta = Signal(int)

    def __init__(self, should_handle, consume_input) -> None:
        super().__init__()
        self._should_handle = should_handle
        self._consume_input = consume_input
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._hook = None
        self._callback = _LowLevelMouseProc(self._dispatch)
        self._user32.SetWindowsHookExW.argtypes = [ctypes.c_int, _LowLevelMouseProc, wintypes.HINSTANCE, wintypes.DWORD]
        self._user32.SetWindowsHookExW.restype = wintypes.HHOOK
        self._user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        self._user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        self._user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        self._user32.CallNextHookEx.restype = ctypes.c_ssize_t
        self._kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        self._kernel32.GetModuleHandleW.restype = wintypes.HMODULE

    @property
    def installed(self) -> bool:
        return self._hook is not None

    def install(self) -> bool:
        if self._hook is not None:
            return True
        module = self._kernel32.GetModuleHandleW(None)
        self._hook = self._user32.SetWindowsHookExW(WH_MOUSE_LL, self._callback, module, 0)
        return self._hook is not None

    def uninstall(self) -> None:
        if self._hook is not None:
            self._user32.UnhookWindowsHookEx(self._hook)
            self._hook = None

    def _dispatch(self, code: int, message: int, parameter: int) -> int:
        if code == HC_ACTION and message == WM_MOUSEWHEEL and self._should_handle():
            data = ctypes.cast(parameter, ctypes.POINTER(_MouseHookData)).contents
            delta = ctypes.c_short((int(data.mouseData) >> 16) & 0xFFFF).value
            if delta:
                self.wheel_delta.emit(delta)
            if self._consume_input():
                return 1
        return int(self._user32.CallNextHookEx(self._hook, code, message, parameter))
