"""SayoDevice API v1 wire protocol (64-byte packets on usage page 0xFF00).

Packet layout (65 bytes passed to hidapi: report ID + 64 wire bytes):
    [0] report_id = 0x02
    [1] cmd
    [2] data_len
    [3 .. 3+data_len-1] payload
    [3+data_len] checksum = sum(bytes[0 .. 3+data_len-1]) & 0xFF

Response mirrors the layout; response cmd == 0 means success, any other
value is a device-side error code.

Sources: Sayobot/Sayo_CLI o2_protocol.cpp, khang06's O3C internals notes,
AustinHay/sayo-configurator (verified against O3C hardware).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

import hid

logger = logging.getLogger(__name__)

SAYO_VID = 0x8089
CONFIG_USAGE_PAGE = 0xFF00
PACKET_SIZE = 64
READ_TIMEOUT_MS = 1000
WRITE_RETRIES = 2

CMD_META_INFO = 0x00
CMD_SAVE = 0x04
CMD_SIMPLE_KEY = 0x06
CMD_DEVICE_NAME = 0x08
CMD_TEXT = 0x0C
CMD_LIGHT = 0x10
CMD_PALETTE = 0x11
CMD_KEY = 0x16
CMD_OPTION = 0xFC
CMD_BOOTLOADER = 0xFF

SAVE_MAGIC = bytes((0x72, 0x96))

KEY_LAYERS = 5
KEY_HEADER_LEN = 16
KEY_LAYER_LEN = 6
KEY_PAYLOAD_LEN = KEY_HEADER_LEN + KEY_LAYERS * KEY_LAYER_LEN  # 46

LAYER_MODE_NONE = 0
LAYER_MODE_KEYBOARD = 1

MODEL_NAMES = {
    0x0002: "O2", 0x0003: "O2C", 0x0004: "O2S",
    0x0005: "O2T-ES", 0x0006: "O2T-QS", 0x0007: "O2 Mini",
    0x0008: "M1T4K", 0x0009: "O3C",
}


class SayoDeviceError(RuntimeError):
    """Base error for everything SayoDevice."""


class SayoNotConnected(SayoDeviceError):
    pass


class SayoTimeout(SayoDeviceError):
    pass


class SayoProtocolError(SayoDeviceError):
    def __init__(self, cmd: int, code: int):
        super().__init__(f"device rejected cmd 0x{cmd:02x} with error code {code}")
        self.cmd = cmd
        self.code = code


@dataclass(slots=True)
class DeviceInfo:
    firmware_version: str
    model_code: int

    @property
    def model_name(self) -> str:
        return MODEL_NAMES.get(self.model_code, f"unknown (0x{self.model_code:04x})")


@dataclass(slots=True)
class KeyLayer:
    mode: int = LAYER_MODE_NONE
    modifier: int = 0          # HID modifier bitmask (ctrl=1, shift=2, alt=4, gui=8)
    keycodes: list[int] = field(default_factory=lambda: [0, 0, 0])  # HID usage IDs

    def pack(self) -> bytes:
        return bytes((self.mode, 0, self.modifier, *self.keycodes[:3]))

    @classmethod
    def unpack(cls, raw: bytes) -> "KeyLayer":
        return cls(mode=raw[0], modifier=raw[2], keycodes=list(raw[3:6]))


@dataclass(slots=True)
class SimpleKey:
    number: int
    type: int = 0
    modifier: int = 0                 # HID modifier bitmask
    keycodes: list[int] = field(default_factory=lambda: [0, 0, 0])


@dataclass(slots=True)
class KeyConfig:
    number: int
    type: int = 0
    site_x: int = 0
    site_y: int = 0
    shape_x: int = 0
    shape_y: int = 0
    shape_r: int = 0
    layers: list[KeyLayer] = field(default_factory=lambda: [KeyLayer() for _ in range(KEY_LAYERS)])

    def pack(self, write: bool) -> bytes:
        head = bytearray(KEY_HEADER_LEN)
        head[0] = 1 if write else 0            # pattern
        head[1] = self.number
        head[2] = self.type
        head[4:6] = self.site_x.to_bytes(2, "little")
        head[6:8] = self.site_y.to_bytes(2, "little")
        head[10:12] = self.shape_x.to_bytes(2, "little")
        head[12:14] = self.shape_y.to_bytes(2, "little")
        head[14:16] = self.shape_r.to_bytes(2, "little")
        body = b"".join(layer.pack() for layer in self.layers[:KEY_LAYERS])
        return bytes(head) + body

    @classmethod
    def unpack(cls, raw: bytes) -> "KeyConfig":
        layers = [
            KeyLayer.unpack(raw[KEY_HEADER_LEN + i * KEY_LAYER_LEN:KEY_HEADER_LEN + (i + 1) * KEY_LAYER_LEN])
            for i in range(KEY_LAYERS)
        ]
        return cls(
            number=raw[1],
            type=raw[2],
            site_x=int.from_bytes(raw[4:6], "little"),
            site_y=int.from_bytes(raw[6:8], "little"),
            shape_x=int.from_bytes(raw[10:12], "little"),
            shape_y=int.from_bytes(raw[12:14], "little"),
            shape_r=int.from_bytes(raw[14:16], "little"),
            layers=layers,
        )


def find_config_interface(vid: int = SAYO_VID, pid: int | None = None) -> dict | None:
    """Locate the vendor config HID interface (usage page 0xFF00).

    Opening by bare VID/PID is wrong — hidapi would grab the first interface,
    which is the keyboard. Must open by path.
    """
    for dev in hid.enumerate(vid, pid or 0):
        if dev.get("usage_page") == CONFIG_USAGE_PAGE:
            return dev
    return None


class SayoProtocol:
    """Synchronous v1 protocol channel. Thread-safe via internal lock."""

    def __init__(self):
        self._handle: hid.device | None = None
        self._lock = threading.Lock()
        self._path: bytes | None = None
        self.info: DeviceInfo | None = None
        self.product: str = ""

    # -- lifecycle -------------------------------------------------------

    def open(self) -> DeviceInfo:
        dev = find_config_interface()
        if dev is None:
            raise SayoNotConnected("no SayoDevice config interface found (vendor 0x8089, usage page 0xFF00)")
        handle = hid.device()
        try:
            handle.open_path(dev["path"])
        except OSError as exc:
            raise SayoNotConnected(f"config interface exists but open failed: {exc}") from exc
        with self._lock:
            self._handle = handle
            self._path = dev["path"]
            self.product = dev.get("product_string") or "SayoDevice"
        self.info = self.device_info()
        logger.info("opened %s (%s, fw %s)", self.product, self.info.model_name, self.info.firmware_version)
        return self.info

    def close(self) -> None:
        with self._lock:
            if self._handle:
                self._handle.close()
            self._handle = None
            self.info = None

    @property
    def is_open(self) -> bool:
        return self._handle is not None

    # -- transport -------------------------------------------------------

    def _xfer(self, cmd: int, payload: bytes = b"") -> bytes:
        """One request/response round trip. Returns response payload."""
        if len(payload) > 60:
            raise ValueError("payload too long for v1 packet")
        packet = bytearray(PACKET_SIZE + 1)
        packet[0] = 0x02  # report ID
        packet[1] = cmd
        packet[2] = len(payload)
        packet[3:3 + len(payload)] = payload
        packet[3 + len(payload)] = sum(packet[:3 + len(payload)]) & 0xFF

        with self._lock:
            if self._handle is None:
                raise SayoNotConnected("device not open")
            last_exc: Exception | None = None
            for attempt in range(1 + WRITE_RETRIES):
                try:
                    self._handle.write(bytes(packet))
                    resp = bytes(self._handle.read(PACKET_SIZE, timeout_ms=READ_TIMEOUT_MS))
                except OSError as exc:
                    # device unplugged mid-transfer
                    self._handle.close()
                    self._handle = None
                    raise SayoNotConnected(f"transfer failed: {exc}") from exc
                if not resp:
                    last_exc = SayoTimeout(f"no response to cmd 0x{cmd:02x} (attempt {attempt + 1})")
                    time.sleep(0.05)
                    continue
                # resp[0] = report id (0x02), resp[1] = status, resp[2] = data_len
                status, length = resp[1], resp[2]
                if status != 0:
                    raise SayoProtocolError(cmd, status)
                return resp[3:3 + length]
            raise last_exc or SayoTimeout(f"cmd 0x{cmd:02x} timed out")

    # -- commands ----------------------------------------------------------

    def device_info(self) -> DeviceInfo:
        now = time.localtime()
        payload = bytes((now.tm_hour, now.tm_min, now.tm_sec, now.tm_wday))
        data = self._xfer(CMD_META_INFO, payload)
        if len(data) < 4:
            raise SayoDeviceError(f"short meta-info response ({len(data)} bytes)")
        version = f"{data[0]}.{data[1]}"
        model = (data[2] << 8) | data[3]
        return DeviceInfo(firmware_version=version, model_code=model)

    def save_to_flash(self) -> None:
        """Persist current RAM config. Without this, changes vanish on unplug."""
        self._xfer(CMD_SAVE, SAVE_MAGIC)

    def read_key(self, number: int) -> KeyConfig:
        """Full key config (cmd 0x16). Unsupported on O3C firmware (error 255)."""
        data = self._xfer(CMD_KEY, bytes((0, number)))
        if len(data) < KEY_PAYLOAD_LEN:
            raise SayoDeviceError(f"short key response for key {number} ({len(data)} bytes)")
        return KeyConfig.unpack(data)

    def read_all_keys(self, limit: int = 16) -> list[KeyConfig]:
        keys = []
        for i in range(limit):
            try:
                keys.append(self.read_key(i))
            except (SayoProtocolError, SayoTimeout):
                break
        return keys

    def write_key(self, config: KeyConfig) -> None:
        self._xfer(CMD_KEY, config.pack(write=True))

    # -- simple key (cmd 0x06) — the binding channel O3C actually supports.
    # Payload: pattern | number | type | retain | modifier | keycode1..3
    # (verified against O3C hardware: default D/F/Esc read back as
    #  07/09/29 at the keycode1 position)

    def read_simple_key(self, number: int) -> SimpleKey:
        data = self._xfer(CMD_SIMPLE_KEY, bytes((0, number)))
        if len(data) < 8:
            raise SayoDeviceError(f"short simple-key response ({len(data)} bytes)")
        return SimpleKey(number=data[1], type=data[2], modifier=data[4], keycodes=list(data[5:8]))

    def read_simple_keys(self, limit: int = 16) -> list["SimpleKey"]:
        keys = []
        for i in range(limit):
            try:
                keys.append(self.read_simple_key(i))
            except (SayoProtocolError, SayoTimeout):
                break
        return keys

    def write_simple_key(self, key: "SimpleKey") -> None:
        payload = bytes((1, key.number, key.type, 0, key.modifier, *key.keycodes[:3]))
        self._xfer(CMD_SIMPLE_KEY, payload)

    def read_lights(self, limit: int = 16) -> list[bytes]:
        lights = []
        for i in range(limit):
            try:
                lights.append(self._xfer(CMD_LIGHT, bytes((0, i))))
            except (SayoProtocolError, SayoTimeout):
                break
        return lights

    def write_light_raw(self, payload: bytes) -> None:
        self._xfer(CMD_LIGHT, payload)

    def set_key_rgb(self, number: int, r: int, g: int, b: int) -> None:
        """Write a static color for one key's lamp entry.

        Verified on O3C hardware: light entry bytes 5/6/7 are R/G/B;
        the rest of the entry (mode, timing params) is preserved from
        a fresh read so only the color changes.
        """
        current = self._xfer(CMD_LIGHT, bytes((0, number)))
        if len(current) < 8:
            raise SayoDeviceError(f"short light response for key {number}")
        entry = bytearray(current)
        entry[0] = 1  # pattern: write
        entry[5], entry[6], entry[7] = r & 0xFF, g & 0xFF, b & 0xFF
        self.write_light_raw(bytes(entry))

    def device_name(self) -> str:
        data = self._xfer(CMD_DEVICE_NAME, bytes((0,)))
        return data[1:].split(b"\x00", 1)[0].decode("utf-8", "replace")

    def set_device_name(self, name: str) -> None:
        encoded = name.encode("utf-8")[:58]
        self._xfer(CMD_DEVICE_NAME, bytes((1,)) + encoded)

    def api_read(self, cmd: int, number: int) -> bytes:
        """Generic pattern/number read for exploring undocumented commands."""
        return self._xfer(cmd, bytes((0, number)))
