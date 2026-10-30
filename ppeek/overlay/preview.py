"""Offscreen HUD preview rendering with staged telemetry data.

Shared by scripts/render_screenshots.py (README PNGs) and the config-hub
skin showcase (theme cards). Loads the same Hud.qml the overlay runs into
a never-shown QQuickView and grabs it, so it works both under
QT_QPA_PLATFORM=offscreen and inside the running main process, and the
previews can't drift from the real overlay.

The hub is built with ``animated=False``: every animation in Hud.qml holds
its resting pose, so each render of a theme looks identical. Output
resolution follows the screen's device pixel ratio (run with
QT_SCALE_FACTOR=2 for 2x README shots).
"""
from __future__ import annotations

import dataclasses
import time
from pathlib import Path

from PyQt6.QtCore import QEventLoop, QUrl
from PyQt6.QtGui import QColor, QGuiApplication, QImage
from PyQt6.QtQuick import QQuickView

from ppeek.osu.telemetry import GameState, TelemetryFrame
from ppeek.overlay.bridge import HubState
from ppeek.overlay.theme import ensure_theme_fonts

HUD_QML = Path(__file__).with_name("Hud.qml")

DEMO_FRAME = TelemetryFrame(
    state=GameState.PLAY,
    connected=True,
    pp=327.0,
    combo=728,
    max_combo=728,
    accuracy=98.64,
    grade="S",
    hits_300=512,
    hits_100=14,
    hits_50=2,
    hits_miss=0,
    hit_errors=[-4.2, 2.1, -8.5, 12.3, -1.0, 5.7, -15.2, 3.3, 7.9, -6.1,
                1.4, -11.8, 9.2, -2.6, 4.8, -7.3, 24.1, -3.9, 0.8, -39.4,
                71.0, -18.6],
    unstable_rate=87.3,
    skin="",
)


def render_theme_preview(skin: str, theme=None) -> QImage:
    """Render one theme's HUD to a transparent ARGB image.

    ``skin`` goes through the overlay's normal skin-name theme resolution;
    pass ``theme`` (an OverlayTheme) instead for themes with no skin
    tie-in (color palettes). Requires a live QGuiApplication.
    """
    ensure_theme_fonts()
    hub = HubState(animated=False)
    hub.on_telemetry_frame(dataclasses.replace(DEMO_FRAME, skin=skin))
    if theme is not None:
        hub.apply_theme_override(theme)
    hub.on_kps(14.0)
    # stagger tick ages so the meter shows its fade, oldest first
    now = time.monotonic()
    count = len(hub._ticks)
    for i, tick in enumerate(hub._ticks):
        tick["born"] = now - (count - 1 - i) * 0.2
    hub.ticksChanged.emit()

    view = QQuickView()
    view.setColor(QColor(0, 0, 0, 0))
    view.rootContext().setContextProperty("hub", hub)
    view.setSource(QUrl.fromLocalFile(str(HUD_QML)))
    if view.status() != QQuickView.Status.Ready:
        raise RuntimeError(f"Hud.qml failed to load: {view.errors()}")
    root = view.rootObject()
    view.resize(int(root.width()), int(root.height()))

    # Canvas items paint asynchronously: the first grab kicks off their
    # paint, the events in between deliver it, the second grab has it
    app = QGuiApplication.instance()
    view.grabWindow()
    for _ in range(5):
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
    img = view.grabWindow()
    view.deleteLater()
    hub.deleteLater()
    return img
