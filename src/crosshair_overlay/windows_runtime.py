from __future__ import annotations

import ctypes
from ctypes import wintypes


TH32CS_SNAPPROCESS = 0x00000002
MAX_PATH = 260
MONITOR_DEFAULTTONEAREST = 2

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


# Resolve and type the Win32 entry points once. Explicit HANDLE return types
# also prevent 64-bit snapshot handles from being truncated to c_int.
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
_kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
_kernel32.Process32FirstW.restype = wintypes.BOOL
_kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
_kernel32.Process32NextW.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL
_user32.GetForegroundWindow.argtypes = []
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.IsWindowVisible.restype = wintypes.BOOL
_user32.IsIconic.argtypes = [wintypes.HWND]
_user32.IsIconic.restype = wintypes.BOOL
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
_user32.GetWindowRect.restype = wintypes.BOOL
_user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.MonitorFromWindow.restype = wintypes.HANDLE
_user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
_user32.GetMonitorInfoW.restype = wintypes.BOOL


def running_process_names() -> set[str]:
    handle = _kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if handle == wintypes.HANDLE(-1).value:
        return set()

    names: set[str] = set()
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    try:
        has_entry = bool(_kernel32.Process32FirstW(handle, ctypes.byref(entry)))
        while has_entry:
            name = str(entry.szExeFile).strip().lower()
            if name:
                names.add(name)
            has_entry = bool(_kernel32.Process32NextW(handle, ctypes.byref(entry)))
    finally:
        _kernel32.CloseHandle(handle)
    return names


def is_foreground_fullscreen() -> bool:
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return False
    if not _user32.IsWindowVisible(hwnd) or _user32.IsIconic(hwnd):
        return False

    rect = RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False

    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width < 320 or height < 200:
        return False

    monitor = _user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    if not monitor:
        return False

    monitor_info = MONITORINFO()
    monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
    if not _user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
        return False

    mrect = monitor_info.rcMonitor
    mwidth = mrect.right - mrect.left
    mheight = mrect.bottom - mrect.top
    if mwidth <= 0 or mheight <= 0:
        return False

    tolerance = 2
    edge_match = (
        abs(rect.left - mrect.left) <= tolerance
        and abs(rect.top - mrect.top) <= tolerance
        and abs(rect.right - mrect.right) <= tolerance
        and abs(rect.bottom - mrect.bottom) <= tolerance
    )
    if edge_match:
        return True

    return width >= int(mwidth * 0.98) and height >= int(mheight * 0.98)


def foreground_monitor_bounds() -> tuple[int, int, int, int] | None:
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    if not _user32.IsWindowVisible(hwnd) or _user32.IsIconic(hwnd):
        return None

    monitor = _user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    if not monitor:
        return None

    monitor_info = MONITORINFO()
    monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
    if not _user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
        return None

    rect = monitor_info.rcMonitor
    return (rect.left, rect.top, rect.right, rect.bottom)


def foreground_window_bounds() -> tuple[int, int, int, int] | None:
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    if not _user32.IsWindowVisible(hwnd) or _user32.IsIconic(hwnd):
        return None

    rect = RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None

    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width < 80 or height < 80:
        return None
    return (rect.left, rect.top, rect.right, rect.bottom)
