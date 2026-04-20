from __future__ import annotations

import ctypes
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence


def _enum_value(value) -> int:
    return int(getattr(value, "value", value))


_USER32 = ctypes.WinDLL("user32", use_last_error=True)
_MODIFIER_MASK = (
    _enum_value(Qt.KeyboardModifier.ShiftModifier)
    | _enum_value(Qt.KeyboardModifier.ControlModifier)
    | _enum_value(Qt.KeyboardModifier.AltModifier)
    | _enum_value(Qt.KeyboardModifier.MetaModifier)
)

_VK_SHIFT = 0x10
_VK_CONTROL = 0x11
_VK_MENU = 0x12
_VK_LWIN = 0x5B
_VK_RWIN = 0x5C


@dataclass(frozen=True)
class HotkeySpec:
    sequence: str
    key_code: int
    require_shift: bool = False
    require_ctrl: bool = False
    require_alt: bool = False
    require_meta: bool = False


def parse_hotkey(sequence: str) -> HotkeySpec | None:
    text = sequence.strip()
    if not text:
        return None

    key_sequence = QKeySequence.fromString(text)
    if key_sequence.count() <= 0:
        return None

    combination = key_sequence[0]
    key = _enum_value(combination.key())
    modifiers = _enum_value(combination.keyboardModifiers()) & _MODIFIER_MASK
    virtual_key = _qt_key_to_virtual_key(key)
    if virtual_key is None:
        return None

    return HotkeySpec(
        sequence=key_sequence.toString(QKeySequence.SequenceFormat.PortableText),
        key_code=virtual_key,
        require_shift=bool(modifiers & _enum_value(Qt.KeyboardModifier.ShiftModifier)),
        require_ctrl=bool(modifiers & _enum_value(Qt.KeyboardModifier.ControlModifier)),
        require_alt=bool(modifiers & _enum_value(Qt.KeyboardModifier.AltModifier)),
        require_meta=bool(modifiers & _enum_value(Qt.KeyboardModifier.MetaModifier)),
    )


def is_hotkey_pressed(spec: HotkeySpec | None) -> bool:
    if spec is None:
        return False
    if spec.require_shift and not _is_key_down(_VK_SHIFT):
        return False
    if spec.require_ctrl and not _is_key_down(_VK_CONTROL):
        return False
    if spec.require_alt and not _is_key_down(_VK_MENU):
        return False
    if spec.require_meta and not (_is_key_down(_VK_LWIN) or _is_key_down(_VK_RWIN)):
        return False
    return _is_key_down(spec.key_code)


def _is_key_down(virtual_key: int) -> bool:
    return bool(_USER32.GetAsyncKeyState(virtual_key) & 0x8000)


def _qt_key_to_virtual_key(key: int) -> int | None:
    if 0x41 <= key <= 0x5A:
        return key
    if 0x30 <= key <= 0x39:
        return key

    mapping = {
        _enum_value(Qt.Key.Key_Space): 0x20,
        _enum_value(Qt.Key.Key_Tab): 0x09,
        _enum_value(Qt.Key.Key_Backtab): 0x09,
        _enum_value(Qt.Key.Key_Return): 0x0D,
        _enum_value(Qt.Key.Key_Enter): 0x0D,
        _enum_value(Qt.Key.Key_Escape): 0x1B,
        _enum_value(Qt.Key.Key_Backspace): 0x08,
        _enum_value(Qt.Key.Key_Insert): 0x2D,
        _enum_value(Qt.Key.Key_Delete): 0x2E,
        _enum_value(Qt.Key.Key_Home): 0x24,
        _enum_value(Qt.Key.Key_End): 0x23,
        _enum_value(Qt.Key.Key_PageUp): 0x21,
        _enum_value(Qt.Key.Key_PageDown): 0x22,
        _enum_value(Qt.Key.Key_Left): 0x25,
        _enum_value(Qt.Key.Key_Up): 0x26,
        _enum_value(Qt.Key.Key_Right): 0x27,
        _enum_value(Qt.Key.Key_Down): 0x28,
        _enum_value(Qt.Key.Key_Minus): 0xBD,
        _enum_value(Qt.Key.Key_Equal): 0xBB,
        _enum_value(Qt.Key.Key_BracketLeft): 0xDB,
        _enum_value(Qt.Key.Key_BracketRight): 0xDD,
        _enum_value(Qt.Key.Key_Backslash): 0xDC,
        _enum_value(Qt.Key.Key_Semicolon): 0xBA,
        _enum_value(Qt.Key.Key_Apostrophe): 0xDE,
        _enum_value(Qt.Key.Key_Comma): 0xBC,
        _enum_value(Qt.Key.Key_Period): 0xBE,
        _enum_value(Qt.Key.Key_Slash): 0xBF,
        _enum_value(Qt.Key.Key_QuoteLeft): 0xC0,
        _enum_value(Qt.Key.Key_Control): _VK_CONTROL,
        _enum_value(Qt.Key.Key_Shift): _VK_SHIFT,
        _enum_value(Qt.Key.Key_Alt): _VK_MENU,
        _enum_value(Qt.Key.Key_Meta): _VK_LWIN,
    }
    if key in mapping:
        return mapping[key]

    if _enum_value(Qt.Key.Key_F1) <= key <= _enum_value(Qt.Key.Key_F24):
        return 0x70 + (key - _enum_value(Qt.Key.Key_F1))

    return None
