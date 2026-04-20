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


def running_process_names() -> set[str]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if handle == wintypes.HANDLE(-1).value:
        return set()

    names: set[str] = set()
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    has_entry = bool(kernel32.Process32FirstW(handle, ctypes.byref(entry)))
    while has_entry:
        name = str(entry.szExeFile).strip().lower()
        if name:
            names.add(name)
        has_entry = bool(kernel32.Process32NextW(handle, ctypes.byref(entry)))

    kernel32.CloseHandle(handle)
    return names


def is_foreground_fullscreen() -> bool:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return False

    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False

    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width < 320 or height < 200:
        return False

    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    if not monitor:
        return False

    monitor_info = MONITORINFO()
    monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
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
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return None

    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    if not monitor:
        return None

    monitor_info = MONITORINFO()
    monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
        return None

    rect = monitor_info.rcMonitor
    return (rect.left, rect.top, rect.right, rect.bottom)
