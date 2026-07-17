"""Skin showcase tab: live-rendered overlay previews as clickable cards.

Two sections: osu! skin tributes (download link + apply) and color
palettes (gruvbox, everforest, nord, tokyo-night, catppuccin, ayu —
apply only). Each card renders the actual OverlayWindow offscreen with
staged demo telemetry (via overlay.preview), so previews always match
the shipped theme code. Previews render lazily on first show to keep
app startup cheap.

Apply writes settings key ``overlay/theme_override``; the overlay
process watches the settings file and swaps its theme live. Empty value
means automatic skin-name matching (the Auto button).

Cards are custom-painted by design (dark, skin-art backdrop) — the rest
of the settings window stays native-themed.
"""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QRectF, QSettings, Qt, QUrl
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
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ppeek.overlay.theme import OverlayTheme, THEMES_BY_NAME, resolve_theme

OVERRIDE_KEY = "overlay/theme_override"


@dataclass(frozen=True)
class SkinEntry:
    title: str
    author: str       # empty for palettes; card then shows "color palette"
    skin_name: str    # fed through skin-name theme resolution ("" for palettes)
    url: str | None   # skin download page; None for palettes
    anim_t: float     # frozen animation-clock phase for the preview
    theme_name: str   # key into THEMES_BY_NAME; drives apply + preview


SKIN_CATALOG: list[SkinEntry] = [
    SkinEntry(
        title="FOOL MOON NIGHT",
        author="Spoo",
        skin_name="FOOL MOON NIGHT",
        url="https://skins.osuck.net/skins/2931",
        anim_t=3.7,
        theme_name="full-moon-night",
    ),
    SkinEntry(
        title="Arona & Plana (Blue Archive)",
        author="Kitazaki Hinata",
        skin_name="hk7205 - Arona & Plana",
        url="https://skins.osuck.net/skins/4434",
        anim_t=2.4,
        theme_name="arona-plana",
    ),
    SkinEntry(
        title="FREEDOM DiVE REiMAGINED",
        author="Spoo",
        skin_name="FREEDOM DiVE REiMAGINED",
        url="https://skins.osuck.net/skins/4062",
        anim_t=5.1,
        theme_name="freedom-dive",
    ),
    SkinEntry(
        title="clearBlack",
        author="FakeCarpetGrass",
        skin_name="- # clearBlack",
        url="https://skins.osuck.net/skins/308",
        anim_t=1.9,
        theme_name="clear-black",
    ),
]

PALETTE_CATALOG: list[SkinEntry] = [
    SkinEntry("Gruvbox", "", "", None, 1.2, "gruvbox"),
    SkinEntry("Everforest", "", "", None, 2.9, "everforest"),
    SkinEntry("Nord", "", "", None, 4.4, "nord"),
    SkinEntry("Tokyo Night", "", "", None, 0.6, "tokyo-night"),
    SkinEntry("Catppuccin", "", "", None, 3.3, "catppuccin"),
    SkinEntry("Ayu", "", "", None, 5.8, "ayu"),
]

_CARD_W = 320
_PREVIEW_H = 180
_FOOTER_H = 54
_RADIUS = 12.0
_MARGIN = 12  # breathing room around the preview inside its zone


def _opaque(c: QColor) -> QColor:
    return QColor(c.red(), c.green(), c.blue())


class SkinCard(QWidget):
    """One showcase card: preview on theme backdrop + title strip + chips."""

    def __init__(self, entry: SkinEntry, on_apply, parent: QWidget | None = None):
        super().__init__(parent)
        self.entry = entry
        self._on_apply = on_apply
        self._theme: OverlayTheme = THEMES_BY_NAME.get(
            entry.theme_name, resolve_theme(entry.skin_name))
        self._preview: QPixmap | None = None
        self._hover = False
        self._hover_chip: str | None = None   # "apply" | "url" | None
        self._applied = False
        self._apply_rect = QRectF()
        self._url_rect = QRectF()
        self.setFixedSize(_CARD_W, _PREVIEW_H + _FOOTER_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        if entry.url:
            self.setToolTip(entry.url)

    def set_preview(self, pixmap: QPixmap) -> None:
        self._preview = pixmap
        self.update()

    def set_applied(self, applied: bool) -> None:
        if applied != self._applied:
            self._applied = applied
            self.update()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self._hover_chip = None
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        chip = None
        if self._apply_rect.contains(pos):
            chip = "apply"
        elif self.entry.url and self._url_rect.contains(pos):
            chip = "url"
        if chip != self._hover_chip:
            self._hover_chip = chip
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if (event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.position().toPoint())):
            pos = event.position()
            if self._apply_rect.contains(pos) or not self.entry.url:
                self._on_apply(self.entry)
            else:
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
        meta = "by " + self.entry.author if self.entry.author else "color palette"
        meta_rect = footer.adjusted(14, 28, -14, -6)
        p.drawText(meta_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, meta)

        # chips, right-aligned: [page ↗] [apply/applied]
        accent = _opaque(self._theme.accent)
        fm = p.fontMetrics()
        chip_h = 18.0
        chip_y = meta_rect.center().y() - chip_h / 2
        right = footer.right() - 14

        apply_text = "applied ✓" if self._applied else "apply"
        aw = fm.horizontalAdvance(apply_text) + 16
        self._apply_rect = QRectF(right - aw, chip_y, aw, chip_h)
        hot = self._hover_chip == "apply" or self._applied
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(accent if hot else QColor(50, 50, 64))
        p.drawRoundedRect(self._apply_rect, chip_h / 2, chip_h / 2)
        p.setPen(QColor(12, 12, 18) if hot else QColor(210, 210, 220))
        p.drawText(self._apply_rect, Qt.AlignmentFlag.AlignCenter, apply_text)
        right -= aw + 8

        if self.entry.url:
            url_text = "page ↗"
            uw = fm.horizontalAdvance(url_text) + 16
            self._url_rect = QRectF(right - uw, chip_y, uw, chip_h)
            p.setPen(QPen(accent if self._hover_chip == "url" else QColor(70, 70, 88), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(self._url_rect, chip_h / 2, chip_h / 2)
            p.setPen(accent if self._hover_chip == "url" else QColor(170, 170, 185))
            p.drawText(self._url_rect, Qt.AlignmentFlag.AlignCenter, url_text)
        else:
            self._url_rect = QRectF()

        # border: accent when applied or hovered, subtle otherwise
        p.setClipping(False)
        border = accent if (self._hover or self._applied) else QColor(60, 60, 75)
        p.setPen(QPen(border, 1.5 if (self._hover or self._applied) else 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(outer, _RADIUS, _RADIUS)
        p.end()


class SkinShowcase(QScrollArea):
    """Grid of theme cards; overlay previews render on first show."""

    def __init__(self, settings: QSettings, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings = settings
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(QLabel("Overlay theme — apply one, or let it follow your skin:"))
        header.addStretch(1)
        self._auto_btn = QPushButton("Auto (match my skin)")
        self._auto_btn.clicked.connect(lambda: self._apply(None))
        header.addWidget(self._auto_btn)
        outer.addLayout(header)

        self._cards: list[SkinCard] = []
        outer.addLayout(self._section("osu! skin tributes", SKIN_CATALOG))
        outer.addSpacing(6)
        outer.addLayout(self._section("Color palettes", PALETTE_CATALOG))
        outer.addStretch(1)
        self.setWidget(container)

        self._rendered = False
        self._refresh_applied()

    def _section(self, label: str, entries: list[SkinEntry]) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(8)
        head = QLabel(label)
        font = head.font()
        font.setBold(True)
        head.setFont(font)
        box.addWidget(head)
        grid = QGridLayout()
        grid.setSpacing(16)
        for i, entry in enumerate(entries):
            card = SkinCard(entry, self._apply)
            self._cards.append(card)
            grid.addWidget(card, i // 2, i % 2, Qt.AlignmentFlag.AlignTop)
        box.addLayout(grid)
        return box

    def _apply(self, entry: SkinEntry | None) -> None:
        self._settings.setValue(OVERRIDE_KEY, entry.theme_name if entry else "")
        self._settings.sync()
        self._refresh_applied()

    def _refresh_applied(self) -> None:
        current = str(self._settings.value(OVERRIDE_KEY, ""))
        for card in self._cards:
            card.set_applied(bool(current) and card.entry.theme_name == current)
        self._auto_btn.setEnabled(bool(current))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._rendered:
            self._rendered = True
            self._render_previews()

    def _render_previews(self) -> None:
        # imported here so the main process only pays for the overlay
        # machinery once the Skins tab is actually opened
        from ppeek.overlay.preview import render_theme_preview

        for card in self._cards:
            entry = card.entry
            theme = None if entry.skin_name else THEMES_BY_NAME[entry.theme_name]
            img = render_theme_preview(entry.skin_name, entry.anim_t, theme=theme)
            card.set_preview(QPixmap.fromImage(img))
