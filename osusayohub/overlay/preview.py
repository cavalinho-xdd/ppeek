"""Offscreen overlay preview rendering with staged telemetry data.

Shared by scripts/render_screenshots.py (README PNGs) and the config-hub
skin showcase (live-rendered cards). Renders an OverlayWindow into a
QImage without ever showing it, so it works both under
QT_QPA_PLATFORM=offscreen and inside the running main process.

Reaches into OverlayWindow private animation state on purpose: previews
must freeze the lerp and the animation clock at a hand-picked phase so
every render of a theme looks identical.
"""
from __future__ import annotations

import dataclasses
import time

from PyQt6.QtGui import QImage, QPainter

from osusayohub.osu.telemetry import GameState, TelemetryFrame
from osusayohub.overlay.window import OverlayWindow

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
                1.4, -11.8, 9.2, -2.6, 4.8, -7.3, 14.1, -3.9, 0.8, -9.4],
    unstable_rate=87.3,
    skin="",
)


def render_theme_preview(skin: str, anim_t: float, scale: int = 2) -> QImage:
    """Render one theme's overlay preview to a transparent ARGB image.

    ``skin`` goes through the overlay's normal skin-name theme resolution;
    ``anim_t`` freezes the scene animation at that clock phase. Requires a
    live QApplication.
    """
    win = OverlayWindow(auto_hide=False)
    win._tick.stop()

    frame = dataclasses.replace(DEMO_FRAME, skin=skin)
    win.on_telemetry_frame(frame)
    win.on_kps(14.0)

    # skip the lerp: show final values immediately
    win._shown_pp = frame.pp
    win._shown_acc = frame.accuracy
    # freeze animation clock at the requested phase
    win._t0 = time.monotonic() - anim_t
    # refresh error-tick timestamps so none have faded out
    now = time.monotonic()
    win._recent_errors.clear()
    for i, err in enumerate(frame.hit_errors):
        win._recent_errors.append((err, now - i * 0.12))

    w, h = win.width(), win.height()
    img = QImage(w * scale, h * scale, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    img.setDevicePixelRatio(scale)
    painter = QPainter(img)
    win.render(painter)
    painter.end()
    win.deleteLater()
    return img
