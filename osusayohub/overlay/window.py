"""Transparent, focus-free overlay: PP, combo, accuracy, hit-error/UR meter, KPS.

Two procedural visual themes (no image assets), auto-selected by the
active osu! skin reported over telemetry (see overlay/theme.py):

- "night" — FULL MOON NIGHT: hand-drawn monochrome ink on a night sky;
  hatched planets, twinkling stars, a crescent moon, water ripples.
- "pastel" — Arona & Plana (Blue Archive): pastel blue on deep navy;
  tilted halo, drifting hollow squares, x-sparks, dot grid.
"""
from __future__ import annotations

import math
import random
import time
from collections import deque

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from osusayohub.osu.telemetry import GameState, TelemetryFrame
from osusayohub.overlay.theme import DEFAULT_THEME, ensure_theme_fonts, resolve_theme

# hit-error meter windows as white intensity steps (approx. standard difficulty)
_ERR_BANDS = [
    (16.0, 200),   # 300 window — brightest
    (64.0, 120),   # 100 window
    (97.0, 60),    # 50 window
]
_ERR_RANGE_MS = 110.0

# pastel grade inks, matching Overlay.qml (SS gold … D blood red)
_GRADE_COLORS = {
    "XH": QColor(233, 209, 139), "X": QColor(233, 209, 139),   # soft gold
    "SH": QColor(159, 198, 234), "S": QColor(159, 198, 234),   # pastel blue
    "A": QColor(169, 217, 162),                                # pastel green
    "B": QColor(234, 185, 140),                                # pastel orange
    "C": QColor(226, 154, 154),                                # washed rose
    "D": QColor(200, 64, 64),                                  # blood red
}


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class OverlayWindow(QWidget):
    """Frameless click-through HUD. All state pushed in via slots, painted at 30 fps."""

    def __init__(self, auto_hide: bool = True):
        super().__init__()
        ensure_theme_fonts()
        self._auto_hide = auto_hide
        self._theme = DEFAULT_THEME

        # target values (from telemetry) and displayed values (animated)
        self._frame = TelemetryFrame()
        self._shown_pp = 0.0
        self._shown_acc = 0.0
        self._ur = 0.0
        self._kps = 0.0
        self._recent_errors: deque[tuple[float, float]] = deque(maxlen=48)  # (error_ms, t)
        self._connected = False
        self._combo_bump_t = 0.0  # monotonic time of last combo increase
        self._t0 = time.monotonic()

        # star field: (x_frac, y_frac, radius, phase, twinkle_speed, is_sparkle)
        rng = random.Random(9)
        self._stars: list[tuple[float, float, float, float, float, bool]] = [
            (rng.random(), rng.random(), rng.uniform(0.5, 1.3),
             rng.uniform(0.0, math.tau), rng.uniform(0.8, 2.2), False)
            for _ in range(34)
        ]
        self._stars += [
            (rng.random(), rng.uniform(0.05, 0.6), rng.uniform(1.6, 2.4),
             rng.uniform(0.0, math.tau), rng.uniform(0.5, 1.2), True)
            for _ in range(5)
        ]

        # pastel-scene particles: (x_frac, y_frac, size, phase, speed, kind)
        # kind: 0 = filled diamond, 1 = hollow square, 2 = "+" spark,
        #       3 = red/pink diamond (sparse pop of the halo-string color)
        prng = random.Random(7205)
        kinds = [0, 0, 1, 1, 2, 0, 1, 2, 3, 0, 1, 0, 2, 1, 3, 0, 1, 2]
        self._pastel_bits: list[tuple[float, float, float, float, float, int]] = [
            (prng.random(), prng.random(), prng.uniform(1.6, 3.4),
             prng.uniform(0.0, math.tau), prng.uniform(0.4, 1.4), kind)
            for kind in kinds
        ]

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
            # real click-through for top-level windows on Windows
            # (WS_EX_TRANSPARENT); WA_TransparentForMouseEvents alone
            # only covers widget-local hit testing
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.resize(320, 170)
        self.move(40, 40)

        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self._animate)
        self._tick.start()

    def _ink(self, alpha: int) -> QColor:
        c = QColor(self._theme.ink)
        c.setAlpha(max(0, min(255, alpha)))
        return c

    # -- inbound slots -------------------------------------------------

    def on_telemetry_frame(self, frame: TelemetryFrame) -> None:
        # empty skin means tosu failed to read it (lazer memory hiccup) —
        # keep the current theme rather than flashing back to the default
        if frame.skin and frame.skin != self._frame.skin:
            self._theme = resolve_theme(frame.skin)
        prev_errors = len(self._frame.hit_errors)
        if frame.combo > self._frame.combo:
            self._combo_bump_t = time.monotonic()
        self._frame = frame
        self._connected = True

        now = time.monotonic()
        for err in frame.hit_errors[prev_errors:]:
            self._recent_errors.append((err, now))

        if frame.unstable_rate > 0:
            self._ur = frame.unstable_rate

        if self._auto_hide:
            should_show = frame.in_gameplay
            if should_show and not self.isVisible():
                self.show()
            elif not should_show and self.isVisible():
                self.hide()
                self._recent_errors.clear()

    def on_telemetry_disconnect(self) -> None:
        self._connected = False

    def on_unstable_rate(self, ur: float) -> None:
        # evdev-derived fallback; telemetry UR wins when present
        if self._frame.unstable_rate <= 0:
            self._ur = ur

    def on_kps(self, kps: float) -> None:
        self._kps = kps

    # -- animation -----------------------------------------------------

    def _animate(self) -> None:
        if not self.isVisible():
            return
        self._shown_pp = _lerp(self._shown_pp, self._frame.pp, 0.25)
        self._shown_acc = _lerp(self._shown_acc, self._frame.accuracy, 0.25)
        cutoff = time.monotonic() - 6.0
        while self._recent_errors and self._recent_errors[0][1] < cutoff:
            self._recent_errors.popleft()
        self.update()

    # -- painting --------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        t = time.monotonic() - self._t0

        # background panel
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, self._theme.bg_top)
        bg.setColorAt(1.0, self._theme.bg_bottom)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(0, 0, w, h), 12, 12)

        # scene behind the numbers
        if self._theme.scene == "pastel":
            self._paint_pastel_scene(p, w, h, t)
        else:
            self._paint_stars(p, w, h, t)
            self._paint_planet(p, w - 52, 36, 20, alpha=150, ring=True)
            self._paint_planet(p, w * 0.38, 16, 6, alpha=110, hatch_step=3)
            self._paint_moon(p, w * 0.56, 22, 8, alpha=170)
            self._paint_ripples(p, w, h, t)
        self._paint_frame_corners(p, w, h)

        if not self._connected:
            p.setPen(self._ink(180))
            wait_font = QFont(self._theme.font, 11)
            wait_font.setItalic(True)
            p.setFont(wait_font)
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                       "waiting for osu!lazer\n(tosu websocket)")
            return

        # PP — hero number with soft glow
        pp_rect = QRectF(16, 8, w - 90, 44)
        pp_text = f"{self._shown_pp:.0f}pp"
        p.setFont(QFont(self._theme.font, 26, QFont.Weight.Bold))
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        p.setPen(self._ink(45))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            p.drawText(pp_rect.translated(dx, dy), flags, pp_text)
        p.setPen(self._ink(255))
        p.drawText(pp_rect, flags, pp_text)

        # grade badge — pastel ink per rank
        grade = self._frame.grade
        if grade:
            p.setPen(_GRADE_COLORS.get(grade, self._theme.ink))
            p.setFont(QFont(self._theme.font, 22, QFont.Weight.Bold))
            p.drawText(QRectF(w - 74, 8, 58, 44), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       grade.replace("H", "").replace("X", "SS"))

        # combo / acc / kps line — combo flashes brighter right after it grows
        bump = max(0.0, 1.0 - (time.monotonic() - self._combo_bump_t) / 0.4)
        p.setPen(self._ink(int(_lerp(200, 255, bump))))
        p.setFont(QFont(self._theme.font, 12, QFont.Weight.Bold if bump > 0.5 else QFont.Weight.Normal))
        p.drawText(16, 70, f"{self._frame.combo}x")
        p.setPen(self._ink(210))
        p.setFont(QFont(self._theme.font, 12))
        p.drawText(QRectF(0, 54, w // 2 + 30, 22), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"{self._shown_acc:.2f}%")
        p.drawText(QRectF(0, 54, w - 16, 22), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"{self._kps:.0f} kps")

        # hit counts — white intensity ladder, red accent for misses
        p.setFont(QFont(self._theme.font, 10))
        f = self._frame
        counts = [
            (f"{f.hits_300}", self._ink(255)),
            (f"{f.hits_100}", self._ink(190)),
            (f"{f.hits_50}", self._ink(130)),
            (f"{f.hits_miss}", QColor(self._theme.miss)),
        ]
        x = 16.0
        for text, color in counts:
            p.setPen(color)
            p.drawText(int(x), 92, text)
            x += p.fontMetrics().horizontalAdvance(text) + 14

        # hit-error meter
        self._paint_error_meter(p, QRectF(16, 104, w - 32, 26))

        # UR readout
        p.setPen(self._ink(210))
        p.setFont(QFont(self._theme.font, 11))
        p.drawText(QRectF(0, 134, w - 16, 24), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"UR {self._ur:5.1f}")

    # -- scene pieces ----------------------------------------------------

    def _paint_stars(self, p: QPainter, w: int, h: int, t: float) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        for fx, fy, r, phase, speed, sparkle in self._stars:
            tw = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * speed + phase))
            x, y = fx * w, fy * h
            if sparkle:
                # four-point twinkle like the hand-drawn sky
                p.setPen(QPen(self._ink(int(190 * tw)), 1))
                s = r * (1.5 + 1.5 * tw)
                p.drawLine(QPointF(x - s, y), QPointF(x + s, y))
                p.drawLine(QPointF(x, y - s), QPointF(x, y + s))
                p.setPen(Qt.PenStyle.NoPen)
            else:
                p.setBrush(self._ink(int(200 * tw)))
                p.drawEllipse(QPointF(x, y), r, r)

    def _accent(self, alpha: int) -> QColor:
        c = QColor(self._theme.accent)
        c.setAlpha(max(0, min(255, alpha)))
        return c

    def _paint_pastel_scene(self, p: QPainter, w: int, h: int, t: float) -> None:
        """Blue Archive motifs, after the Arona & Plana skin art: diagonal
        stripe clusters in opposite corners, dot grids, a red halo with its
        trailing string, pastel diamonds/squares and +/x sparks."""
        self._paint_stripe_cluster(p, w - 14, 14, mirror=False)
        self._paint_stripe_cluster(p, 14, h - 14, mirror=True)

        # dot grids — top-left and near the bottom-right stripe cluster
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._ink(110))
        for gy in range(4):
            for gx in range(6):
                p.drawEllipse(QPointF(14 + gx * 5.0, 14 + gy * 5.0), 0.9, 0.9)
                p.drawEllipse(QPointF(w - 44 + gx * 5.0, h - 30 + gy * 5.0), 0.9, 0.9)

        # Arona's red halo, floating center-top where the crescent moon lives
        # in the night theme, with the red string trailing off the panel
        halo_x, halo_y = w * 0.56, 20.0
        pulse = 0.5 + 0.5 * math.sin(t * 1.4)
        red = QColor(self._theme.deco_red)

        string_path = QPainterPath(QPointF(halo_x - 16, halo_y + 4))
        string_path.cubicTo(QPointF(w * 0.40, h * 0.50),
                            QPointF(w * 0.16, h * 0.42),
                            QPointF(-6, h * 0.86))
        red.setAlpha(70)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(red, 1.1))
        p.drawPath(string_path)

        # tiny heart hanging off the string, like the chibi speech bubble
        anchor = string_path.pointAtPercent(0.72)
        hx, hy = anchor.x(), anchor.y()
        heart = QPainterPath(QPointF(hx, hy + 2.6))
        heart.cubicTo(QPointF(hx - 3.4, hy - 0.6), QPointF(hx - 1.8, hy - 3.0),
                      QPointF(hx, hy - 1.0))
        heart.cubicTo(QPointF(hx + 1.8, hy - 3.0), QPointF(hx + 3.4, hy - 0.6),
                      QPointF(hx, hy + 2.6))
        red.setAlpha(150)
        p.fillPath(heart, red)

        p.save()
        p.translate(halo_x, halo_y)
        p.rotate(-14)
        p.setBrush(Qt.BrushStyle.NoBrush)
        red.setAlpha(int(_lerp(180, 240, pulse)))
        p.setPen(QPen(red, 2.4))
        p.drawEllipse(QPointF(0, 0), 20, 7)
        red.setAlpha(80)
        p.setPen(QPen(red, 1.0))
        p.drawEllipse(QPointF(0, 0), 25, 9.5)
        p.restore()

        # scattered particles: pastel diamonds, hollow squares, +/x sparks,
        # with sparse red diamonds popping against the blue
        for fx, fy, size, phase, speed, kind in self._pastel_bits:
            tw = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * speed + phase))
            x, y = fx * w, fy * h
            if kind == 0:
                p.save()
                p.translate(x, y)
                p.rotate(45.0)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(self._ink(int(170 * tw)))
                p.drawRect(QRectF(-size / 2, -size / 2, size, size))
                p.restore()
            elif kind == 1:
                p.save()
                p.translate(x, y)
                p.rotate(math.degrees(phase) + t * speed * 8)
                side = size * 2.4
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(self._accent(int(150 * tw)), 1.0))
                p.drawRect(QRectF(-side / 2, -side / 2, side, side))
                p.restore()
            elif kind == 2:
                p.setPen(QPen(self._ink(int(190 * tw)), 1.2))
                s = size * (0.8 + 0.8 * tw)
                p.drawLine(QPointF(x - s, y), QPointF(x + s, y))
                p.drawLine(QPointF(x, y - s), QPointF(x, y + s))
            else:
                p.save()
                p.translate(x, y)
                p.rotate(45.0)
                red_bit = QColor(self._theme.deco_red)
                red_bit.setAlpha(int(180 * tw))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(red_bit)
                s = size * 0.8
                p.drawRect(QRectF(-s / 2, -s / 2, s, s))
                p.restore()

        # x-sparks from the shared star field keep the sky twinkling
        for fx, fy, r, phase, speed, sparkle in self._stars:
            if not sparkle:
                continue
            tw = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * speed + phase))
            x, y = fx * w, fy * h
            p.setPen(QPen(self._ink(int(190 * tw)), 1.2))
            s = r * (1.2 + 1.2 * tw)
            p.drawLine(QPointF(x - s, y - s), QPointF(x + s, y + s))
            p.drawLine(QPointF(x - s, y + s), QPointF(x + s, y - s))

    def _paint_stripe_cluster(self, p: QPainter, cx: float, cy: float,
                              mirror: bool) -> None:
        """Diagonal stack of rounded bars, like the skin's corner decoration.
        Mix of filled pastel, filled accent and outlined slate bars."""
        p.save()
        p.translate(cx, cy)
        p.rotate(135.0 if mirror else -45.0)
        bars = [
            (0.0, -10.0, 26.0, 5.0, "ink", 60),
            (6.0, -2.0, 40.0, 6.5, "accent", 90),
            (-8.0, 6.0, 30.0, 5.0, "ink", 130),
            (10.0, 14.0, 20.0, 4.0, "outline", 110),
            (-4.0, 21.0, 34.0, 5.5, "accent", 55),
        ]
        for bx, by, bw, bh, style, alpha in bars:
            rect = QRectF(bx - bw / 2, by, bw, bh)
            if style == "outline":
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(self._ink(alpha), 1.0))
            else:
                color = self._ink(alpha) if style == "ink" else self._accent(alpha)
                p.setBrush(color)
                p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(rect, bh / 2, bh / 2)
        p.restore()

    def _paint_planet(self, p: QPainter, cx: float, cy: float, r: float,
                      alpha: int, hatch_step: float = 4.0, ring: bool = False) -> None:
        """Hatched line-art planet; optional Saturn-style triple ring."""
        p.save()
        ring_pen = QPen(self._ink(int(alpha * 0.9)), 1.2)
        ring_rects = [QRectF(-r * k, -r * k * 0.32, r * k * 2, r * k * 0.64)
                      for k in (1.55, 1.75, 1.95)]
        if ring:
            # far half of the ring, behind the planet body
            p.save()
            p.translate(cx, cy)
            p.rotate(-18)
            p.setPen(ring_pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for rect in ring_rects:
                p.drawArc(rect, 0, 180 * 16)
            p.restore()

        body = QPainterPath()
        body.addEllipse(QPointF(cx, cy), r, r)
        p.setClipPath(body)
        p.fillPath(body, self._theme.body_fill)
        # wavy horizontal hatching, clipped to the disc
        p.setPen(QPen(self._ink(int(alpha * 0.55)), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        y, i = -r + hatch_step, 0
        while y < r:
            bow = 0.15 * r * math.sin(i * 1.7)
            p.drawArc(QRectF(cx - r, cy + y + bow - 2, 2 * r, 4), 0, 180 * 16)
            y += hatch_step
            i += 1
        p.setClipping(False)

        p.setPen(QPen(self._ink(alpha), 1.4))
        p.drawEllipse(QPointF(cx, cy), r, r)

        if ring:
            # near half of the ring, in front of the planet body
            p.translate(cx, cy)
            p.rotate(-18)
            p.setPen(ring_pen)
            for rect in ring_rects:
                p.drawArc(rect, 180 * 16, 180 * 16)
        p.restore()

    def _paint_moon(self, p: QPainter, cx: float, cy: float, r: float, alpha: int) -> None:
        disc = QPainterPath()
        disc.addEllipse(QPointF(cx, cy), r, r)
        bite = QPainterPath()
        bite.addEllipse(QPointF(cx + r * 0.45, cy - r * 0.25), r * 0.85, r * 0.85)
        p.fillPath(disc.subtracted(bite), self._ink(int(alpha * 0.85)))
        p.setPen(QPen(self._ink(alpha), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

    def _paint_ripples(self, p: QPainter, w: int, h: int, t: float) -> None:
        """Concentric water rings drifting outward along the bottom edge."""
        cx, cy = w / 2.0, h - 4.0
        gap = 16.0
        max_rx = w * 0.55
        rx = 14.0 + (t * 9.0) % gap
        p.setBrush(Qt.BrushStyle.NoBrush)
        while rx < max_rx:
            fade = 1.0 - rx / max_rx
            p.setPen(QPen(self._ink(int(70 * fade)), 1))
            p.drawArc(QRectF(cx - rx, cy - rx * 0.18, rx * 2, rx * 0.36), 0, 180 * 16)
            rx += gap

    def _paint_frame_corners(self, p: QPainter, w: int, h: int) -> None:
        """Sketchbook corner brackets, like the album-cover frame."""
        m, s = 7.0, 12.0
        p.setPen(QPen(self._ink(140), 1.2))
        for x, y, dx, dy in ((m, m, 1, 1), (w - m, m, -1, 1),
                             (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            p.drawLine(QPointF(x, y), QPointF(x + dx * s, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + dy * s))

    def _paint_error_meter(self, p: QPainter, rect: QRectF) -> None:
        mid_x = rect.center().x()
        bar_y = rect.center().y()

        # ink-shade windows, widest first so narrow bands draw on top
        for width_ms, shade in reversed(_ERR_BANDS):
            half = (width_ms / _ERR_RANGE_MS) * (rect.width() / 2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._ink(shade // 2))
            p.drawRoundedRect(QRectF(mid_x - half, bar_y - 3, half * 2, 6), 3, 3)

        # center line
        p.setPen(QPen(self._ink(200), 2))
        p.drawLine(int(mid_x), int(rect.top()), int(mid_x), int(rect.bottom()))

        # recent hits as fading ticks, brightness matches the window they fall in
        now = time.monotonic()
        for err, t in self._recent_errors:
            age = now - t
            alpha = max(0, int(230 * (1.0 - age / 6.0)))
            offset = max(-1.0, min(1.0, err / _ERR_RANGE_MS)) * (rect.width() / 2)
            shade = 255
            for width_ms, band_shade in _ERR_BANDS:
                if abs(err) <= width_ms:
                    shade = min(255, band_shade + 55)
                    break
            color = self._ink(min(alpha, shade))
            p.setPen(QPen(color, 2))
            x = mid_x + offset
            p.drawLine(int(x), int(rect.top() + 4), int(x), int(rect.bottom() - 4))
