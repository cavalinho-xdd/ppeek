"""Qt bridge object exposing live HUD state to the QML overlay."""
from __future__ import annotations

import time

from PyQt6.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor

from ppeek.osu.telemetry import TelemetryFrame
from ppeek.overlay.theme import DEFAULT_THEME, resolve_theme


def _hex(color: QColor) -> str:
    return color.name(QColor.NameFormat.HexArgb)

# anchor flag values from wlr-layer-shell (LayerShellQt::Window::Anchor)
ANCHOR_TOP, ANCHOR_BOTTOM, ANCHOR_LEFT, ANCHOR_RIGHT = 1, 2, 4, 8

ANCHOR_PRESETS = {
    "top-left": ANCHOR_TOP | ANCHOR_LEFT,
    "top-right": ANCHOR_TOP | ANCHOR_RIGHT,
    "bottom-left": ANCHOR_BOTTOM | ANCHOR_LEFT,
    "bottom-right": ANCHOR_BOTTOM | ANCHOR_RIGHT,
    "top-center": ANCHOR_TOP,
    "bottom-center": ANCHOR_BOTTOM,
}

_ERR_RANGE_MS = 110.0
_ERR_BANDS = [(16.0, "#46b4ff"), (64.0, "#78dc5a"), (97.0, "#f0c846")]


class HubState(QObject):
    """Single context object bound into QML as `hub`."""

    frameChanged = pyqtSignal()
    ticksChanged = pyqtSignal()
    layoutChanged = pyqtSignal()
    themeChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._frame = TelemetryFrame()
        self._theme = DEFAULT_THEME
        self._skin_theme = DEFAULT_THEME       # what the active skin resolves to
        self._theme_override = None            # OverlayTheme | None; wins over skin
        self._connected = False
        self._ur = 0.0
        self._kps = 0.0
        self._ticks: list[dict] = []  # {"pos": -1..1, "color": str, "born": float}
        self._anchor = ANCHOR_PRESETS["bottom-right"]
        self._margin_x = 24
        self._margin_y = 24
        self._auto_hide = True

        self._age_timer = QTimer(self)
        self._age_timer.setInterval(100)
        self._age_timer.timeout.connect(self._age_ticks)
        self._age_timer.start()

    # -- inbound ---------------------------------------------------------

    def on_telemetry_frame(self, frame: TelemetryFrame) -> None:
        # empty skin means tosu failed to read it (lazer memory hiccup) —
        # keep the current theme rather than flashing back to the default
        if frame.skin and frame.skin != self._frame.skin:
            self._skin_theme = resolve_theme(frame.skin)
            if self._theme_override is None and self._skin_theme is not self._theme:
                self._theme = self._skin_theme
                self.themeChanged.emit()
        prev = len(self._frame.hit_errors)
        # a fresh play resets the array; resync instead of replaying all
        if len(frame.hit_errors) < prev:
            prev = 0
            self._ticks.clear()
        # tosu keeps the last play's hitErrorArray outside gameplay — only
        # convert new errors into ticks while actually playing
        if not frame.in_gameplay:
            prev = len(frame.hit_errors)
        now = time.monotonic()
        for err in frame.hit_errors[prev:]:
            color = "#eb5a5a"
            for width, band_color in _ERR_BANDS:
                if abs(err) <= width:
                    color = band_color
                    break
            pos = max(-1.0, min(1.0, err / _ERR_RANGE_MS))
            self._ticks.append({"pos": pos, "color": color, "born": now})
        self._ticks = self._ticks[-48:]

        self._frame = frame
        self._connected = True
        if frame.unstable_rate > 0:
            self._ur = frame.unstable_rate
        self.frameChanged.emit()
        self.ticksChanged.emit()

    def on_telemetry_disconnect(self) -> None:
        self._connected = False
        self.frameChanged.emit()

    def on_fallback_ur(self, ur: float) -> None:
        if self._frame.unstable_rate <= 0:
            self._ur = ur
            self.frameChanged.emit()

    def on_kps(self, kps: float) -> None:
        if abs(kps - self._kps) > 0.01:
            self._kps = kps
            self.frameChanged.emit()

    def apply_theme_override(self, theme) -> None:
        """Manual theme (from settings) beats skin resolution; None = auto."""
        self._theme_override = theme
        effective = theme if theme is not None else self._skin_theme
        if effective is not self._theme:
            self._theme = effective
            self.themeChanged.emit()

    def apply_layout(self, anchor_name: str, margin_x: int, margin_y: int, auto_hide: bool) -> None:
        self._anchor = ANCHOR_PRESETS.get(anchor_name, self._anchor)
        self._margin_x = margin_x
        self._margin_y = margin_y
        self._auto_hide = auto_hide
        self.layoutChanged.emit()
        self.frameChanged.emit()

    def _age_ticks(self) -> None:
        if not self._ticks:
            return
        cutoff = time.monotonic() - 6.0
        alive = [t for t in self._ticks if t["born"] >= cutoff]
        if len(alive) != len(self._ticks):
            self._ticks = alive
        self.ticksChanged.emit()  # re-emit so QML updates fade opacity

    # -- QML-facing properties -------------------------------------------

    @pyqtProperty(bool, notify=frameChanged)
    def connected(self) -> bool:
        return self._connected

    @pyqtProperty(bool, notify=frameChanged)
    def visible(self) -> bool:
        if not self._auto_hide:
            return True
        return self._connected and self._frame.in_gameplay

    @pyqtProperty(float, notify=frameChanged)
    def pp(self) -> float:
        return self._frame.pp

    @pyqtProperty(int, notify=frameChanged)
    def combo(self) -> int:
        return self._frame.combo

    @pyqtProperty(float, notify=frameChanged)
    def accuracy(self) -> float:
        return self._frame.accuracy

    @pyqtProperty(str, notify=frameChanged)
    def grade(self) -> str:
        g = self._frame.grade
        return {"X": "SS", "XH": "SS", "SH": "S"}.get(g, g)

    @pyqtProperty(float, notify=frameChanged)
    def ur(self) -> float:
        return self._ur

    @pyqtProperty(float, notify=frameChanged)
    def kps(self) -> float:
        return self._kps

    @pyqtProperty(int, notify=frameChanged)
    def hits300(self) -> int:
        return self._frame.hits_300

    @pyqtProperty(int, notify=frameChanged)
    def hits100(self) -> int:
        return self._frame.hits_100

    @pyqtProperty(int, notify=frameChanged)
    def hits50(self) -> int:
        return self._frame.hits_50

    @pyqtProperty(int, notify=frameChanged)
    def hitsMiss(self) -> int:
        return self._frame.hits_miss

    @pyqtProperty("QVariantList", notify=ticksChanged)
    def errorTicks(self) -> list:
        now = time.monotonic()
        return [
            {"pos": t["pos"], "color": t["color"], "age": min(1.0, (now - t["born"]) / 6.0)}
            for t in self._ticks
        ]

    # NOTE: layer-shell margins are emulated with transparent padding inside
    # the window — QMargins values don't marshal through QML bindings.
    @pyqtProperty(int, notify=layoutChanged)
    def anchorFlags(self) -> int:
        return self._anchor

    @pyqtProperty(int, notify=layoutChanged)
    def marginX(self) -> int:
        return self._margin_x

    @pyqtProperty(int, notify=layoutChanged)
    def marginY(self) -> int:
        return self._margin_y

    @pyqtProperty(bool, notify=layoutChanged)
    def anchoredLeft(self) -> bool:
        return bool(self._anchor & ANCHOR_LEFT)

    @pyqtProperty(bool, notify=layoutChanged)
    def anchoredRight(self) -> bool:
        return bool(self._anchor & ANCHOR_RIGHT)

    @pyqtProperty(bool, notify=layoutChanged)
    def anchoredTop(self) -> bool:
        return bool(self._anchor & ANCHOR_TOP)

    # -- theme (skin-driven) ----------------------------------------------

    @pyqtProperty(str, notify=themeChanged)
    def scene(self) -> str:
        return self._theme.scene

    @pyqtProperty(str, notify=themeChanged)
    def ink(self) -> str:
        return _hex(self._theme.ink)

    @pyqtProperty(str, notify=themeChanged)
    def inkDim(self) -> str:
        return _hex(self._theme.ink.darker(135))

    @pyqtProperty(str, notify=themeChanged)
    def paper(self) -> str:
        c = QColor(self._theme.body_fill)
        c.setAlpha(240)
        return _hex(c)

    @pyqtProperty(str, notify=themeChanged)
    def accent(self) -> str:
        return _hex(self._theme.accent)

    @pyqtProperty(str, notify=themeChanged)
    def decoRed(self) -> str:
        return _hex(self._theme.deco_red)

    @pyqtProperty(str, notify=themeChanged)
    def missColor(self) -> str:
        return _hex(self._theme.miss)

    @pyqtProperty(str, notify=themeChanged)
    def themeFont(self) -> str:
        return self._theme.font

    @pyqtProperty(str, constant=True)
    def fontPath(self) -> str:
        return self._font_uri("Gaegu-Regular.ttf")

    @pyqtProperty(str, constant=True)
    def pastelFontPath(self) -> str:
        return self._font_uri("Quicksand-VariableFont.ttf")

    @pyqtProperty(str, constant=True)
    def freedomFontPath(self) -> str:
        return self._font_uri("Fredoka-VariableFont.ttf")

    @staticmethod
    def _font_uri(filename: str) -> str:
        from pathlib import Path

        font = Path(__file__).parent.parent / "assets" / "fonts" / filename
        return font.as_uri() if font.exists() else ""
