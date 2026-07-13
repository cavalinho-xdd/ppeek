"""High-level SayoDevice facade used by the config hub.

Wraps the v1 wire protocol (protocol.py) with binding/RGB/persistence
operations expressed in Qt terms. All methods raise SayoDeviceError
subclasses on failure; callers surface the message in the UI.
"""
from __future__ import annotations

import logging

from osusayohub.device import hid_usage
from osusayohub.device.protocol import (
    DeviceInfo,
    SayoDeviceError,
    SayoNotConnected,
    SayoProtocol,
    SayoProtocolError,
    SimpleKey,
)

logger = logging.getLogger(__name__)

__all__ = ["SayoDevice", "SayoDeviceError", "SayoNotConnected", "Binding"]


class Binding:
    """One key's binding in Qt terms."""

    def __init__(self, number: int, qt_key: int | None, modifier: int = 0, raw: SimpleKey | None = None):
        self.number = number
        self.qt_key = qt_key
        self.modifier = modifier
        self.raw = raw

    def display(self) -> str:
        from PyQt6.QtGui import QKeySequence

        if self.qt_key:
            return QKeySequence(self.qt_key).toString()
        if self.raw and any(self.raw.keycodes):
            return " ".join(f"0x{k:02x}" for k in self.raw.keycodes if k)
        return ""


class SayoDevice:
    def __init__(self):
        self._proto = SayoProtocol()

    # -- lifecycle ---------------------------------------------------------

    def open(self) -> None:
        self._proto.open()

    def close(self) -> None:
        self._proto.close()

    @property
    def is_open(self) -> bool:
        return self._proto.is_open

    def description(self) -> str:
        if not self._proto.is_open:
            return "not connected"
        info = self._proto.info
        product = self._proto.product
        if info:
            return f"{product} — fw {info.firmware_version}"
        return product

    @property
    def info(self) -> DeviceInfo | None:
        return self._proto.info

    # -- key bindings --------------------------------------------------------

    def read_bindings(self) -> list[Binding]:
        bindings = []
        for key in self._proto.read_simple_keys():
            primary = next((k for k in key.keycodes if k), 0)
            bindings.append(
                Binding(
                    number=key.number,
                    qt_key=hid_usage.hid_to_qt(primary),
                    modifier=key.modifier,
                    raw=key,
                )
            )
        return bindings

    def set_key_binding(self, number: int, qt_key: int) -> None:
        """Bind a key to a Qt key code (RAM only — call save_to_flash to persist)."""
        usage = hid_usage.qt_to_hid(qt_key) if qt_key else 0
        if qt_key and usage is None:
            raise SayoDeviceError(f"key has no HID usage mapping: {qt_key:#x}")
        existing = self._proto.read_simple_key(number)
        existing.modifier = 0
        existing.keycodes = [usage or 0, 0, 0]  # first keycode slot, factory layout
        self._proto.write_simple_key(existing)

    # -- RGB ---------------------------------------------------------------

    def set_rgb(self, number: int, r: int, g: int, b: int) -> None:
        self._proto.set_key_rgb(number, r, g, b)

    def light_count(self) -> int:
        return len(self._proto.read_lights())

    # -- persistence / info ----------------------------------------------

    def save_to_flash(self) -> None:
        self._proto.save_to_flash()

    def device_name(self) -> str:
        try:
            return self._proto.device_name()
        except (SayoProtocolError, SayoDeviceError):
            return ""

    def set_device_name(self, name: str) -> None:
        self._proto.set_device_name(name)

    # -- unsupported on O3C -------------------------------------------------

    def set_rapid_trigger(self, enabled: bool, sensitivity_mm: float) -> None:
        raise SayoDeviceError(
            "rapid trigger is not supported by O3C firmware "
            "(mechanical switches, no analog sensing)"
        )
