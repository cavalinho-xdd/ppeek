"""Skin showcase tab: live-rendered overlay previews as clickable cards.

Each card renders the actual OverlayWindow offscreen with staged demo
telemetry (via overlay.preview), so previews always match the shipped
theme code. Clicking a card opens the skin's download page in the
system browser. Previews render lazily on first show to keep app
startup cheap.

Cards are custom-painted by design (dark, skin-art backdrop) — the rest
of the settings window stays native-themed.
"""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QRectF, Qt, QUrl
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QGridLayout, QScrollArea, QVBoxLayout, QWidget

from osusayohub.overlay.theme import OverlayTheme, resolve_theme


@dataclass(frozen=True)
class SkinEntry:
    title: str
    author: str      # empty when unknown; card then shows the site domain
    skin_name: str   # fed through the overlay's skin-name theme resolution
    url: str
    anim_t: float    # frozen animation-clock phase for the preview


SKIN_CATALOG: list[SkinEntry] = [
    SkinEntry(
        title="FOOL MOON NIGHT",
        author="Spoo",
        skin_name="FOOL MOON NIGHT",
        url="https://skins.osuck.net/skins/2931",
        anim_t=3.7,
    ),
    SkinEntry(
        title="Arona & Plana (Blue Archive)",
        author="Kitazaki Hinata",
        skin_name="hk7205 - Arona & Plana",
        url="https://skins.osuck.net/skins/4434",
        anim_t=2.4,
    ),
    SkinEntry(
        title="FREEDOM DiVE REiMAGINED",
        author="Spoo",
        skin_name="FREEDOM DiVE REiMAGINED",
        url="https://skins.osuck.net/skins/4062",
        anim_t=5.1,
    ),
    SkinEntry(
        title="clearBlack",
        author="FakeCarpetGrass",
        skin_name="- # clearBlack",
        url="https://skins.osuck.net/skins/308",
        anim_t=1.9,
    ),
]

_CARD_W = 320
_PREVIEW_H = 180
_FOOTER_H = 54
_RADIUS = 12.0
_MARGIN = 12  # breathing room around the preview inside its zone


def _opaque(c: QColor) -> QColor:
    return QColor(c.red(), c.green(), c.blue())


class SkinCard(QWidget):
    """One clickable showcase card: preview on theme backdrop + title strip."""

    def __init__(self, entry: SkinEntry, parent: QWidget | None = None):
        super().__init__(parent)
        self.entry = entry
        self._theme: OverlayTheme = resolve_theme(entry.skin_name)
        self._preview: QPixmap | None = None
        self._hover = False
        self.setFixedSize(_CARD_W, _PREVIEW_H + _FOOTER_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(entry.url)

    def set_preview(self, pixmap: QPixmap) -> None:
        self._preview = pixmap
        self.update()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if (event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.position().toPoint())):
            QDesktopServices.openUrl(QUrl(self.entry.url))
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(outer, _RADIUS, _RADIUS)
        p.setClipPath(path)

        # preview zone: the theme's own background gradient, opaque
        zone = QRectF(0, 0, self.width(), _PREVIEW_H)
        grad = QLinearGradient(zone.topLeft(), zone.bottomLeft())
        grad.setColorAt(0.0, _opaque(self._theme.bg_top).lighter(130))
        grad.setColorAt(1.0, _opaque(self._theme.bg_bottom))
        p.fillRect(zone, grad)

        if self._preview is not None:
            avail = zone.adjusted(_MARGIN, _MARGIN, -_MARGIN, -_MARGIN)
            pm = self._preview
            logical_w = pm.width() / pm.devicePixelRatio()
            logical_h = pm.height() / pm.devicePixelRatio()
            k = min(avail.width() / logical_w, avail.height() / logical_h, 1.0)
            w, h = logical_w * k, logical_h * k
            target = QRectF(zone.center().x() - w / 2, zone.center().y() - h / 2, w, h)
            p.drawPixmap(target, pm, QRectF(pm.rect()))

        # footer strip
        footer = QRectF(0, _PREVIEW_H, self.width(), _FOOTER_H)
        p.fillRect(footer, QColor(20, 20, 28) if not self._hover else QColor(28, 28, 40))

        title_font = QFont(self.font())
        title_font.setPointSizeF(10.5)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(QColor(235, 235, 242))
        text_rect = footer.adjusted(14, 8, -14, -26)
        title = p.fontMetrics().elidedText(
            self.entry.title, Qt.TextElideMode.ElideRight, int(text_rect.width()))
        p.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

        meta_font = QFont(self.font())
        meta_font.setPointSizeF(8.5)
        p.setFont(meta_font)
        p.setPen(QColor(150, 150, 165))
        meta = "by " + self.entry.author if self.entry.author else "skins.osuck.net"
        meta_rect = footer.adjusted(14, 28, -14, -6)
        p.drawText(meta_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, meta)
        p.setPen(QColor(*_accent_rgb(self._theme)) if self._hover else QColor(120, 120, 135))
        p.drawText(meta_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   "download ↗")

        # border: theme accent on hover, subtle otherwise
        p.setClipping(False)
        border = _opaque(self._theme.accent) if self._hover else QColor(60, 60, 75)
        p.setPen(QPen(border, 1.5 if self._hover else 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(outer, _RADIUS, _RADIUS)
        p.end()


def _accent_rgb(theme: OverlayTheme) -> tuple[int, int, int]:
    c = theme.accent
    return c.red(), c.green(), c.blue()


class SkinShowcase(QScrollArea):
    """Grid of skin cards; overlay previews render on first show."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(16, 16, 16, 16)

        grid = QGridLayout()
        grid.setSpacing(16)
        self._cards: list[SkinCard] = []
        for i, entry in enumerate(SKIN_CATALOG):
            card = SkinCard(entry)
            self._cards.append(card)
            grid.addWidget(card, i // 2, i % 2, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(grid)
        outer.addStretch(1)
        self.setWidget(container)

        self._rendered = False

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._rendered:
            self._rendered = True
            self._render_previews()

    def _render_previews(self) -> None:
        # imported here so the main process only pays for the overlay
        # machinery once the Skins tab is actually opened
        from osusayohub.overlay.preview import render_theme_preview

        for card in self._cards:
            img = render_theme_preview(card.entry.skin_name, card.entry.anim_t)
            card.set_preview(QPixmap.fromImage(img))
