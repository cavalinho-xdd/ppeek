"""Qt key <-> USB HID keyboard usage ID translation (usage page 0x07)."""
from __future__ import annotations

from PyQt6.QtCore import Qt

# HID modifier bitmask bits (left-hand variants)
MOD_CTRL = 0x01
MOD_SHIFT = 0x02
MOD_ALT = 0x04
MOD_GUI = 0x08

_QT_TO_HID: dict[int, int] = {}
_HID_TO_QT: dict[int, int] = {}


def _add(qt_key: Qt.Key, usage: int) -> None:
    _QT_TO_HID[qt_key.value] = usage
    _HID_TO_QT.setdefault(usage, qt_key.value)


# letters: HID 0x04..0x1D = a..z
for i in range(26):
    _add(Qt.Key(Qt.Key.Key_A.value + i), 0x04 + i)
# digits: HID 0x1E..0x27 = 1..9,0
for i in range(9):
    _add(Qt.Key(Qt.Key.Key_1.value + i), 0x1E + i)
_add(Qt.Key.Key_0, 0x27)
# F-keys: HID 0x3A..0x45 = F1..F12
for i in range(12):
    _add(Qt.Key(Qt.Key.Key_F1.value + i), 0x3A + i)
# F13..F24: HID 0x68..0x73
for i in range(12):
    _add(Qt.Key(Qt.Key.Key_F13.value + i), 0x68 + i)

_add(Qt.Key.Key_Return, 0x28)
_add(Qt.Key.Key_Enter, 0x28)
_add(Qt.Key.Key_Escape, 0x29)
_add(Qt.Key.Key_Backspace, 0x2A)
_add(Qt.Key.Key_Tab, 0x2B)
_add(Qt.Key.Key_Space, 0x2C)
_add(Qt.Key.Key_Minus, 0x2D)
_add(Qt.Key.Key_Equal, 0x2E)
_add(Qt.Key.Key_BracketLeft, 0x2F)
_add(Qt.Key.Key_BracketRight, 0x30)
_add(Qt.Key.Key_Backslash, 0x31)
_add(Qt.Key.Key_Semicolon, 0x33)
_add(Qt.Key.Key_Apostrophe, 0x34)
_add(Qt.Key.Key_QuoteLeft, 0x35)
_add(Qt.Key.Key_Comma, 0x36)
_add(Qt.Key.Key_Period, 0x37)
_add(Qt.Key.Key_Slash, 0x38)
_add(Qt.Key.Key_CapsLock, 0x39)
_add(Qt.Key.Key_Print, 0x46)
_add(Qt.Key.Key_ScrollLock, 0x47)
_add(Qt.Key.Key_Pause, 0x48)
_add(Qt.Key.Key_Insert, 0x49)
_add(Qt.Key.Key_Home, 0x4A)
_add(Qt.Key.Key_PageUp, 0x4B)
_add(Qt.Key.Key_Delete, 0x4C)
_add(Qt.Key.Key_End, 0x4D)
_add(Qt.Key.Key_PageDown, 0x4E)
_add(Qt.Key.Key_Right, 0x4F)
_add(Qt.Key.Key_Left, 0x50)
_add(Qt.Key.Key_Down, 0x51)
_add(Qt.Key.Key_Up, 0x52)


def qt_to_hid(qt_key: int) -> int | None:
    return _QT_TO_HID.get(qt_key)


def hid_to_qt(usage: int) -> int | None:
    return _HID_TO_QT.get(usage)


def hid_usage_name(usage: int) -> str:
    from PyQt6.QtGui import QKeySequence

    qt_key = hid_to_qt(usage)
    if qt_key is None:
        return f"0x{usage:02x}" if usage else ""
    return QKeySequence(qt_key).toString()
