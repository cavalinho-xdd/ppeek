"""Transparent, focus-free overlay: PP, combo, accuracy, hit-error/UR meter, KPS.

Procedural visual themes (no image assets), auto-selected by the
active osu! skin reported over telemetry (see overlay/theme.py):

- "night" — FULL MOON NIGHT: hand-drawn monochrome ink on a night sky;
  hatched planets, twinkling stars, a crescent moon, water ripples.
- "pastel" — Arona & Plana (Blue Archive): pastel blue on deep navy;
  tilted halo, drifting hollow squares, x-sparks, dot grid.
- "freedom" — FREEDOM DiVE REiMAGINED: cosmic blue with blob planets,
  rainbow shooting arrows, white confetti, golden sparkle stars.
- "clearblack" — clearBlack: true black with rainbow-ring crosshair
  hitcircles looping their approach circles, and a drifting blue-violet
  cursor glow.
"""
from __future__ import annotations

import math
import random
import time
from collections import deque

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

from ppeek.osu.telemetry import GameState, TelemetryFrame
from ppeek.overlay.theme import DEFAULT_THEME, ensure_theme_fonts, resolve_theme

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
        self._skin_theme = DEFAULT_THEME       # what the active skin resolves to
        self._theme_override: object = None    # OverlayTheme | None; wins over skin

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

        # freedom scene: diamond confetti (x_frac, y_frac, size, phase, speed, rotation)
        frng = random.Random(1222)
        self._freedom_confetti: list[tuple[float, float, float, float, float, float]] = [
            (frng.random(), frng.random(), frng.uniform(1.5, 3.5),
             frng.uniform(0.0, math.tau), frng.uniform(0.6, 1.8), frng.uniform(0, 360))
            for _ in range(14)
        ]
        # freedom golden sparkle stars (x_frac, y_frac, size, phase, speed)
        self._freedom_sparkles: list[tuple[float, float, float, float, float]] = [
            (frng.random(), frng.random(), frng.uniform(2.0, 4.5),
             frng.uniform(0.0, math.tau), frng.uniform(0.5, 1.6))
            for _ in range(6)
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
            self._skin_theme = resolve_theme(frame.skin)
            if self._theme_override is None:
                self._theme = self._skin_theme
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

    def apply_theme_override(self, theme) -> None:
        """Manual theme (from settings) beats skin resolution; None = auto."""
        self._theme_override = theme
        self._theme = theme if theme is not None else self._skin_theme
        self.update()

    def apply_layout(self, anchor_name: str, margin_x: int, margin_y: int, auto_hide: bool) -> None:
        self._auto_hide = auto_hide
        screen = self.screen()
        if not screen:
            from PyQt6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
        if not screen:
            return
            
        geom = screen.availableGeometry()
        w, h = self.width(), self.height()
        
        if "left" in anchor_name:
            x = geom.left() + margin_x
        elif "right" in anchor_name:
            x = geom.right() - w - margin_x
        else:
            x = geom.center().x() - w // 2
            
        if "top" in anchor_name:
            y = geom.top() + margin_y
        elif "bottom" in anchor_name:
            y = geom.bottom() - h - margin_y
        else:
            y = geom.center().y() - h // 2
            
        self.move(int(x), int(y))

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
        elif self._theme.scene == "freedom":
            self._paint_freedom_scene(p, w, h, t)
        elif self._theme.scene == "clearblack":
            self._paint_clearblack_scene(p, w, h, t)
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

    def _paint_freedom_scene(self, p: QPainter, w: int, h: int, t: float) -> None:
        """Cosmic scene from FREEDOM DiVE REiMAGINED by Spoo:
        cute blob planets with rainbow rings, shooting star arrows,
        white diamond confetti, golden sparkle stars, and the skin's
        BTMC tag (the skin is a tribute to BTMC — former top player,
        now host of the osu! Roundtable tournaments)."""
        self._paint_stars(p, w, h, t)

        # shooting star arrows radiating from the corners (like the skin art)
        self._paint_shooting_arrows(p, w, h, t)

        # white diamond confetti scattered across the sky
        for fx, fy, size, phase, speed, rot in self._freedom_confetti:
            tw = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * speed + phase))
            x, y = fx * w, fy * h
            p.save()
            p.translate(x, y)
            p.rotate(rot + t * speed * 15)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, int(160 * tw)))
            s = size * 0.7
            p.drawRect(QRectF(-s / 2, -s / 2, s, s))
            p.restore()

        # golden four-point sparkle stars (like the cursor glow)
        for fx, fy, size, phase, speed in self._freedom_sparkles:
            tw = 0.2 + 0.8 * (0.5 + 0.5 * math.sin(t * speed + phase))
            x, y = fx * w, fy * h
            gold = QColor(255, 220, 80, int(220 * tw))
            s = size * (0.8 + 1.2 * tw)
            p.setPen(QPen(gold, 1.5))
            p.drawLine(QPointF(x - s, y), QPointF(x + s, y))
            p.drawLine(QPointF(x, y - s), QPointF(x, y + s))
            # diagonal arms at half intensity for six-point effect
            ds = s * 0.5
            gold.setAlpha(int(130 * tw))
            p.setPen(QPen(gold, 1.0))
            p.drawLine(QPointF(x - ds, y - ds), QPointF(x + ds, y + ds))
            p.drawLine(QPointF(x - ds, y + ds), QPointF(x + ds, y - ds))

        # three blob planets (big squinty >w<, medium gentle ˆ_ˆ, tiny peeking from edge)
        self._paint_blob_planet(p, w - 38, 30, 18, t, 0)   # big one, top-right
        self._paint_blob_planet(p, w * 0.32, 16, 8, t, 1)  # medium, top-left
        self._paint_blob_planet(p, 6, h * 0.6, 6, t, 2)    # tiny, peeking from left

        self._paint_btmc_tag(p, 18, h - 14, t)

    def _paint_btmc_tag(self, p: QPainter, x: float, y: float, t: float) -> None:
        """Small dark rounded badge with bold BTMC lettering, echoing the
        tag stitched into the skin art. (x, y) is the text baseline."""
        p.save()
        bob = math.sin(t * 1.1) * 1.2
        p.translate(x, y + bob)
        p.rotate(-4)

        font = QFont(self._theme.font)
        font.setPointSizeF(8.0)
        font.setWeight(QFont.Weight.ExtraBold)
        p.setFont(font)
        fm = p.fontMetrics()
        text_w = fm.horizontalAdvance("BTMC")
        text_h = fm.capHeight()
        pad_x, pad_y = 7.0, 5.0
        rect = QRectF(0, -text_h - pad_y, text_w + pad_x * 2, text_h + pad_y * 2)

        # deep navy badge with a faint cyan rim, like the skin's tag
        p.setPen(QPen(QColor(150, 230, 255, 90), 1.0))
        p.setBrush(QColor(16, 24, 58, 235))
        p.drawRoundedRect(rect, 4.0, 4.0)

        # lettering: faint cyan glow offset under crisp white
        p.setPen(QColor(120, 210, 255, 110))
        p.drawText(QPointF(pad_x + 1.0, 1.0), "BTMC")
        p.setPen(QColor(255, 255, 255))
        p.drawText(QPointF(pad_x, 0.0), "BTMC")
        p.restore()

    def _paint_shooting_arrows(self, p: QPainter, w: int, h: int, t: float) -> None:
        """Thick rainbow arrow bands shooting across the panel, like the skin art."""
        # two arrows: one from bottom-left going up-right, one from top-right going left
        arrows = [
            (QPointF(-8, h + 4), QPointF(w * 0.45, h * 0.35), 14, 0),
            (QPointF(w + 8, -4), QPointF(w * 0.55, h * 0.7), 10, 1),
        ]
        for start, end, thickness, seed in arrows:
            # pulsing opacity
            pulse = 0.15 + 0.12 * math.sin(t * 1.3 + seed * 2.5)
            grad = QLinearGradient(start, end)
            grad.setColorAt(0.0, QColor(255, 80, 60, int(255 * pulse)))    # red
            grad.setColorAt(0.25, QColor(255, 200, 50, int(255 * pulse)))  # yellow
            grad.setColorAt(0.5, QColor(100, 230, 100, int(255 * pulse)))  # green
            grad.setColorAt(0.75, QColor(80, 180, 255, int(255 * pulse)))  # blue
            grad.setColorAt(1.0, QColor(180, 100, 255, int(255 * pulse)))  # purple
            p.setPen(QPen(grad, thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(start, end)

    def _paint_blob_planet(self, p: QPainter, cx: float, cy: float, r: float, t: float, seed: int) -> None:
        """Cute white blob planet with rainbow ring and face, matching skin art."""
        p.save()
        p.translate(cx, cy)
        pulse = math.sin(t * 1.5 + seed) * 0.06
        wobble = math.sin(t * 0.8 + seed * 1.7) * 4
        p.rotate(wobble)
        p.scale(1 + pulse, 1 - pulse)

        # rainbow ring gradient matching the skin (red→yellow→green→cyan→blue→purple)
        grad = QLinearGradient(QPointF(-r * 2.2, 0), QPointF(r * 2.2, 0))
        grad.setColorAt(0.0, QColor(255, 100, 60))
        grad.setColorAt(0.2, QColor(255, 200, 50))
        grad.setColorAt(0.4, QColor(100, 230, 100))
        grad.setColorAt(0.6, QColor(80, 220, 255))
        grad.setColorAt(0.8, QColor(100, 120, 255))
        grad.setColorAt(1.0, QColor(200, 100, 255))

        ring_angle = 15 + t * 25 * (1 if seed % 2 == 0 else -1)
        ring_rect = QRectF(-r * 1.9, -r * 0.5, r * 3.8, r * 1.0)

        # ring back half (behind the body)
        p.save()
        p.rotate(ring_angle)
        p.setPen(QPen(grad, r * 0.3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(ring_rect, 0, 180 * 16)
        p.restore()

        # warm cream body with subtle blush (like the actual skin art)
        body = QPainterPath()
        body.addEllipse(QPointF(0, 0), r, r)
        body_grad = QLinearGradient(QPointF(-r, -r), QPointF(r, r))
        body_grad.setColorAt(0.0, QColor(255, 250, 240, 245))   # warm cream top
        body_grad.setColorAt(0.5, QColor(255, 245, 235, 250))   # cream middle
        body_grad.setColorAt(1.0, QColor(255, 230, 220, 235))   # warm peach bottom (blush)
        p.fillPath(body, body_grad)
        p.setPen(QPen(QColor(200, 190, 180, 80), 1.0))
        p.drawPath(body)

        # face — different expressions per planet (matching the skin art faces)
        face_color = QColor(40, 40, 60)
        p.setBrush(Qt.BrushStyle.NoBrush)
        lw = max(1.2, r * 0.1)
        p.setPen(QPen(face_color, lw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        if seed == 0:
            # big planet: squinty happy >w< face (like the main blob in the art)
            # left eye: >
            p.drawLine(QPointF(-r * 0.45, -r * 0.25), QPointF(-r * 0.2, -r * 0.05))
            p.drawLine(QPointF(-r * 0.45, r * 0.15), QPointF(-r * 0.2, -r * 0.05))
            # right eye: <
            p.drawLine(QPointF(r * 0.45, -r * 0.25), QPointF(r * 0.2, -r * 0.05))
            p.drawLine(QPointF(r * 0.45, r * 0.15), QPointF(r * 0.2, -r * 0.05))
            # w mouth (cat smile)
            mouth = QPainterPath(QPointF(-r * 0.2, r * 0.2))
            mouth.quadTo(QPointF(-r * 0.1, r * 0.35), QPointF(0, r * 0.22))
            mouth.quadTo(QPointF(r * 0.1, r * 0.35), QPointF(r * 0.2, r * 0.2))
            p.drawPath(mouth)
            # pink tongue peeking out
            tongue = QPainterPath()
            tongue.addEllipse(QPointF(0, r * 0.3), r * 0.07, r * 0.06)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(240, 130, 140))
            p.fillPath(tongue, QColor(240, 130, 140))
        elif seed == 1:
            # medium planet: gentle ˆ_ˆ (happy closed eyes, like the bottom-right blob)
            p.drawArc(QRectF(-r * 0.45, -r * 0.25, r * 0.35, r * 0.25), 0, 180 * 16)
            p.drawArc(QRectF(r * 0.1, -r * 0.25, r * 0.35, r * 0.25), 0, 180 * 16)
            # gentle curve mouth
            p.drawArc(QRectF(-r * 0.15, r * 0.05, r * 0.3, r * 0.2), 180 * 16, 180 * 16)
        else:
            # tiny planet: dot eyes, small o mouth (surprised/peeking)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(face_color)
            p.drawEllipse(QPointF(-r * 0.25, -r * 0.1), r * 0.08, r * 0.08)
            p.drawEllipse(QPointF(r * 0.25, -r * 0.1), r * 0.08, r * 0.08)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(face_color, lw))
            p.drawEllipse(QPointF(0, r * 0.2), r * 0.1, r * 0.08)

        # ring front half (in front of the body)
        p.save()
        p.rotate(ring_angle)
        p.setPen(QPen(grad, r * 0.3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(ring_rect, 180 * 16, 180 * 16)
        p.restore()

        p.restore()

    def _paint_clearblack_scene(self, p: QPainter, w: int, h: int, t: float) -> None:
        """clearBlack by ononokie ships no bitmap decoration at all — the
        whole skin is one crosshair hitcircle with a full-spectrum rainbow
        ring and a matching approach circle, on a true-black playfield.
        The scene leans entirely on that one motif: three of those
        hitcircles (looping their own approach circles), the shared
        twinkling +/dot field standing in for a scattered playfield, and
        a drifting cursor with the skin's blue-violet glow."""
        self._paint_stars(p, w, h, t)
        self._paint_hitcircle(p, w - 40, 30, 18, t, 0)
        self._paint_hitcircle(p, w * 0.30, 15, 9, t, 1)
        self._paint_hitcircle(p, 10, h * 0.64, 6, t, 2)
        self._paint_cb_cursor(p, w, h, t)

    def _paint_hitcircle(self, p: QPainter, cx: float, cy: float, r: float,
                         t: float, seed: int) -> None:
        """One clearBlack hitcircle: looping approach circle, near-black
        body, full-spectrum rainbow ring (its combo colours run the whole
        hue wheel — skin.ini Combo1..5 are just five samples of it),
        crisp white overlay ring, and the center crosshair."""
        # approach circle: shrinks in, fades in, then loops — same rhythm
        # as the real thing bearing down on a note
        period = 1.7 + 0.15 * seed
        phase = ((t + seed * 0.6) % period) / period
        ar = r * (2.15 - 1.15 * phase)
        aalpha = int(200 * min(1.0, phase * 2.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(self._ink(aalpha), 1.1))
        p.drawEllipse(QPointF(cx, cy), ar, ar)

        body = QPainterPath()
        body.addEllipse(QPointF(cx, cy), r, r)
        p.fillPath(body, self._theme.body_fill)

        grad = QConicalGradient(cx, cy, (t * 24 + seed * 70) % 360)
        stops = 12
        for i in range(stops + 1):
            hue = int(360 * i / stops) % 360
            grad.setColorAt(i / stops, QColor.fromHsv(hue, 190, 255))
        p.setPen(QPen(QBrush(grad), max(1.6, r * 0.14)))
        p.drawEllipse(QPointF(cx, cy), r, r)

        p.setPen(QPen(self._ink(210), 1.0))
        p.drawEllipse(QPointF(cx, cy), r * 0.88, r * 0.88)

        glow = QRadialGradient(QPointF(cx, cy), r * 0.5)
        glow_c = QColor(self._theme.accent)
        glow_c.setAlpha(120)
        glow_edge = QColor(self._theme.accent)
        glow_edge.setAlpha(0)
        glow.setColorAt(0.0, glow_c)
        glow.setColorAt(1.0, glow_edge)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(cx, cy), r * 0.5, r * 0.5)

        cs = r * 0.22
        p.setPen(QPen(self._ink(235), 1.4))
        p.drawLine(QPointF(cx - cs, cy), QPointF(cx + cs, cy))
        p.drawLine(QPointF(cx, cy - cs), QPointF(cx, cy + cs))

    def _paint_cb_cursor(self, p: QPainter, w: int, h: int, t: float) -> None:
        """Wandering cursor glow, like the skin's soft blue-violet cursor.png,
        drifting a slow lissajous path with a fading trail."""
        def pos(tt: float) -> tuple[float, float]:
            x = w * (0.18 + 0.64 * (0.5 + 0.5 * math.sin(tt * 0.35)))
            y = h * (0.68 + 0.16 * math.sin(tt * 0.55 + 1.3))
            return x, y

        trail = QPainterPath()
        for i in range(10, -1, -1):
            tx, ty = pos(t - i * 0.05)
            if i == 10:
                trail.moveTo(tx, ty)
            else:
                trail.lineTo(tx, ty)
        p.setPen(QPen(self._accent(70), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(trail)

        cx, cy = pos(t)
        glow = QRadialGradient(QPointF(cx, cy), 9)
        c0 = QColor(self._theme.accent)
        c0.setAlpha(210)
        c1 = QColor(self._theme.accent)
        c1.setAlpha(0)
        glow.setColorAt(0.0, c0)
        glow.setColorAt(1.0, c1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(cx, cy), 9, 9)
        p.setBrush(self._ink(235))
        p.drawEllipse(QPointF(cx, cy), 2.2, 2.2)

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
