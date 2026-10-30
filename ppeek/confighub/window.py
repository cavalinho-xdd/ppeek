"""Settings window: overlay position/behavior, themes, input source, about.

One dark style for the whole window (STYLE below), shared with the theme
cards in confighub.skins, so it looks the same on every platform. Writes
settings; the overlay process watches the settings file and applies
changes live.
"""
from __future__ import annotations

import sys

from PyQt6.QtCore import QRectF, QSettings, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ppeek.confighub.skins import OVERRIDE_KEY, SKIN_CATALOG, SkinShowcase
from ppeek.overlay.theme import DEFAULT_THEME, THEMES_BY_NAME, ensure_theme_fonts

# palette — the deep navy of the app icon, its cyan as the one accent
BG = "#12141c"
SIDEBAR = "#0d0f16"
SURFACE = "#1a1d28"
SURFACE_HOVER = "#222636"
BORDER = "#2a2e3e"
TEXT = "#e6e8f0"
TEXT_DIM = "#8d93a8"
ACCENT = "#7cc4ff"
ON_ACCENT = "#0b1020"

STYLE = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}
QLabel {{ background: transparent; }}
QLabel[role="title"] {{ font-size: 20px; font-weight: 600; }}
QLabel[role="subtitle"] {{ color: {TEXT_DIM}; }}
QLabel[role="section"] {{ color: {TEXT_DIM}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
QLabel[role="hint"] {{ color: {TEXT_DIM}; font-size: 12px; }}

QListWidget#nav {{
    background: {SIDEBAR}; border: none; outline: none; padding: 4px 10px;
}}
QListWidget#nav::item {{
    padding: 8px 10px; margin: 1px 0; border-radius: 8px; color: {TEXT_DIM};
}}
QListWidget#nav::item:hover {{ background: {SURFACE}; color: {TEXT}; }}
QListWidget#nav::item:selected {{ background: {SURFACE_HOVER}; color: {TEXT}; }}
QWidget#sidebar {{ background: {SIDEBAR}; }}
QWidget#sidebar QLabel {{ background: {SIDEBAR}; }}

QFrame[role="card"] {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
}}
QFrame[role="card"] QLabel, QFrame[role="card"] QCheckBox {{ background: transparent; }}

QPushButton {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 6px 14px;
}}
QPushButton:hover {{ background: {SURFACE_HOVER}; }}
QPushButton:checked {{ background: {ACCENT}; color: {ON_ACCENT}; border-color: {ACCENT}; }}
QPushButton[role="corner"] {{ padding: 0; min-height: 30px; }}

QSpinBox, QComboBox {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 5px 8px; min-height: 20px;
}}
QSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {BORDER}; selection-background-color: {SURFACE_HOVER};
}}

QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid {BORDER}; background: {BG};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""

# (label, settings value) — laid out as the 3x2 corner picker grid
ANCHORS = [
    ("Top left", "top-left"), ("Top center", "top-center"), ("Top right", "top-right"),
    ("Bottom left", "bottom-left"), ("Bottom center", "bottom-center"), ("Bottom right", "bottom-right"),
]

# tray supervisor status → (sidebar text, dot color); keys match core.app
STATUS_LOOK = {
    "waiting": ("Waiting for osu!", "#808080"),
    "attaching": ("Attaching tosu…", "#e0a030"),
    "running": ("tosu attached", "#40c060"),
}


def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("ppeek")
    except PackageNotFoundError:  # frozen bundle without dist metadata
        return ""


def _label(text: str, role: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", role)
    label.setWordWrap(role in ("subtitle", "hint"))
    return label


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setProperty("role", "card")
    box = QVBoxLayout(frame)
    box.setContentsMargins(18, 16, 18, 18)
    box.setSpacing(10)
    return frame, box


def _page(title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
    page = QWidget()
    box = QVBoxLayout(page)
    box.setContentsMargins(28, 24, 28, 24)
    box.setSpacing(6)
    box.addWidget(_label(title, "title"))
    box.addWidget(_label(subtitle, "subtitle"))
    box.addSpacing(14)
    return page, box


class PositionPreview(QWidget):
    """Mini screen showing where the HUD sits, drawn to scale."""

    SCREEN = QSize(1920, 1080)  # reference resolution for the proportions

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._hud: QPixmap | None = None
        self._anchor = "bottom-right"
        self._mx = self._my = 24
        self.setMinimumSize(320, 180)

    def set_hud(self, pixmap: QPixmap) -> None:
        self._hud = pixmap
        self.update()

    def set_layout(self, anchor: str, mx: int, my: int) -> None:
        self._anchor, self._mx, self._my = anchor, mx, my
        self.update()

    def heightForWidth(self, w: int) -> int:
        return int(w * 9 / 16)

    def hasHeightForWidth(self) -> bool:
        return True

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self.width()
        h = min(self.height(), int(w * 9 / 16))
        screen = QRectF(0.5, 0.5, w - 1, h - 1)
        path = QPainterPath()
        path.addRoundedRect(screen, 10, 10)
        p.fillPath(path, QColor("#2a3046"))
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawPath(path)
        p.setPen(QColor(TEXT_DIM))
        p.drawText(screen.adjusted(12, 8, -12, -8),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "osu!")

        k = screen.width() / self.SCREEN.width()
        hud_w, hud_h = 300 * k, 150 * k
        mx, my = self._mx * k, self._my * k
        if "left" in self._anchor:
            x = screen.left() + mx
        elif "right" in self._anchor:
            x = screen.right() - hud_w - mx
        else:
            x = screen.center().x() - hud_w / 2
        y = screen.top() + my if "top" in self._anchor else screen.bottom() - hud_h - my
        target = QRectF(x, y, hud_w, hud_h)

        if self._hud is not None:
            p.drawPixmap(target, self._hud, QRectF(self._hud.rect()))
        else:
            p.setPen(QPen(QColor(ACCENT), 1))
            p.setBrush(QColor(ACCENT).darker(300))
            p.drawRoundedRect(target, 3, 3)
        p.end()


class SettingsWindow(QWidget):
    def __init__(self, settings: QSettings):
        super().__init__()
        ensure_theme_fonts()
        self.setWindowTitle("PPeek Settings")
        self.setStyleSheet(STYLE)
        palette = self.palette()  # rich-text links ignore the stylesheet
        palette.setColor(palette.ColorRole.Link, QColor(ACCENT))
        self.setPalette(palette)
        self.resize(940, 640)
        self._settings = settings
        self._preview_rendered_for: str | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- sidebar -------------------------------------------------------
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(190)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 22, 0, 16)
        side.setSpacing(14)

        brand = QLabel("PPeek")
        brand_font = QFont("Quicksand")
        brand_font.setPixelSize(24)
        brand_font.setBold(True)
        brand.setFont(brand_font)
        brand.setContentsMargins(22, 0, 0, 0)
        side.addWidget(brand)

        self._nav = QListWidget()
        self._nav.setObjectName("nav")
        side.addWidget(self._nav, 1)

        self._status = QLabel()
        self._status.setContentsMargins(22, 0, 12, 0)
        self._status.setProperty("role", "hint")
        side.addWidget(self._status)
        self.set_status("waiting")

        root.addWidget(sidebar)

        self._pages = QStackedWidget()
        root.addWidget(self._pages, 1)
        self._nav.currentRowChanged.connect(self._pages.setCurrentIndex)

        self._add_page("Overlay", self._build_overlay_page())
        self.showcase = SkinShowcase(settings, on_applied=self._refresh_preview)
        self._add_page("Themes", self._wrap_showcase(self.showcase))
        self._add_page("Input", self._build_input_page())
        self._add_page("About", self._build_about_page())
        self._nav.setCurrentRow(0)

    # -- pages -------------------------------------------------------------

    def _add_page(self, name: str, page: QWidget) -> None:
        item = QListWidgetItem(name)
        item.setSizeHint(QSize(0, 36))
        self._nav.addItem(item)
        self._pages.addWidget(page)

    def _build_overlay_page(self) -> QWidget:
        page, box = _page("Overlay", "Where the HUD sits and when it shows. Changes apply live.")
        s = self._settings

        row = QHBoxLayout()
        row.setSpacing(16)

        preview_card, preview_box = _card()
        preview_box.addWidget(_label("PREVIEW", "section"))
        self._position_preview = PositionPreview()
        preview_box.addWidget(self._position_preview, 1)
        row.addWidget(preview_card, 3)

        pos_card, pos_box = _card()
        pos_box.addWidget(_label("SCREEN CORNER", "section"))
        grid = QGridLayout()
        grid.setSpacing(6)
        self._anchor_group = QButtonGroup(self)
        saved_anchor = str(s.value("overlay/anchor", "bottom-right"))
        for i, (label, value) in enumerate(ANCHORS):
            btn = QPushButton()
            btn.setProperty("role", "corner")
            btn.setProperty("anchor", value)
            btn.setToolTip(label)
            btn.setAccessibleName(label)
            btn.setCheckable(True)
            btn.setChecked(value == saved_anchor)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._anchor_group.addButton(btn, i)
            grid.addWidget(btn, i // 3, i % 3)
        self._anchor_group.idToggled.connect(lambda _id, on: on and self._save())
        pos_box.addLayout(grid)

        pos_box.addSpacing(8)
        pos_box.addWidget(_label("OFFSET", "section"))
        offsets = QGridLayout()
        offsets.setHorizontalSpacing(10)
        self.margin_x = self._offset_spin(int(s.value("overlay/margin_x", 24)))
        self.margin_y = self._offset_spin(int(s.value("overlay/margin_y", 24)))
        offsets.addWidget(QLabel("Horizontal"), 0, 0)
        offsets.addWidget(self.margin_x, 0, 1)
        offsets.addWidget(QLabel("Vertical"), 1, 0)
        offsets.addWidget(self.margin_y, 1, 1)
        pos_box.addLayout(offsets)
        pos_box.addStretch(1)
        row.addWidget(pos_card, 2)
        box.addLayout(row)

        box.addSpacing(16)
        behavior_card, behavior_box = _card()
        self.auto_hide = QCheckBox("Show only during gameplay")
        self.auto_hide.setChecked(s.value("overlay/auto_hide", True, type=bool))
        self.auto_hide.toggled.connect(self._save)
        behavior_box.addWidget(self.auto_hide)
        if sys.platform == "win32":
            hint = ("Run osu!lazer in borderless or windowed fullscreen. "
                    "No overlay can draw over exclusive fullscreen.")
        else:
            hint = ("On Wayland with layer-shell-qt the HUD renders on the overlay layer, "
                    "above fullscreen games. On X11 it's an always-on-top window.")
        behavior_box.addWidget(_label(hint, "hint"))
        box.addWidget(behavior_card)
        box.addStretch(1)

        self._sync_position_preview()
        return page

    def _offset_spin(self, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 4000)
        spin.setSuffix(" px")
        spin.setValue(value)
        spin.valueChanged.connect(self._save)
        return spin

    def _wrap_showcase(self, showcase: QWidget) -> QWidget:
        page, box = _page(
            "Themes",
            "The overlay follows the osu! skin you play with. "
            "Pick a theme to override that, or go back to following your skin.")
        box.addWidget(showcase, 1)
        return page

    def _build_input_page(self) -> QWidget:
        page, box = _page("Input", "Where key presses for KPS come from.")
        card, card_box = _card()
        # evdev input source exists only on Linux; elsewhere KPS comes from
        # tosu's keyOverlay counters and there is nothing to pick
        self.input_source = QComboBox()
        if sys.platform == "linux":
            card_box.addWidget(_label("KEYBOARD DEVICE", "section"))
            card_box.addWidget(self.input_source)
            card_box.addWidget(_label(
                "Read directly through evdev, so presses count even while osu! has focus. "
                "Pick the keyboard (or keypad) you tap with.", "hint"))
        else:
            self.input_source.hide()
            card_box.addWidget(_label(
                "KPS comes from tosu's key overlay counters. Nothing to set up here.", "hint"))
        box.addWidget(card)
        box.addStretch(1)
        return page

    def _build_about_page(self) -> QWidget:
        page, box = _page("About", f"PPeek {_version()} — live PP overlay for osu!lazer.")
        card, card_box = _card()
        card_box.addWidget(_label("SKIN TRIBUTES", "section"))
        for entry in SKIN_CATALOG:
            link = QLabel(f'<a href="{entry.url}">{entry.title}</a> '
                          f'<span style="color:{TEXT_DIM}">by {entry.author}</span>')
            link.setOpenExternalLinks(True)
            card_box.addWidget(link)
        card_box.addSpacing(6)
        card_box.addWidget(_label(
            "Themes are original, procedurally painted tributes. No skin assets are "
            "copied or redistributed. Live game data comes from tosu. osu! is a "
            "trademark of ppy Pty Ltd; this is an unofficial fan project.", "hint"))
        box.addWidget(card)
        box.addStretch(1)
        return page

    # -- state -------------------------------------------------------------

    def set_status(self, status: str) -> None:
        text, color = STATUS_LOOK.get(status, STATUS_LOOK["waiting"])
        self._status.setText(f'<span style="color:{color}">●</span>&nbsp; {text}')

    def _current_anchor(self) -> str:
        btn = self._anchor_group.checkedButton()
        return btn.property("anchor") if btn else "bottom-right"

    def _save(self, *_args) -> None:
        self._settings.setValue("overlay/auto_hide", self.auto_hide.isChecked())
        self._settings.setValue("overlay/anchor", self._current_anchor())
        self._settings.setValue("overlay/margin_x", self.margin_x.value())
        self._settings.setValue("overlay/margin_y", self.margin_y.value())
        self._settings.sync()
        self._sync_position_preview()

    def _sync_position_preview(self) -> None:
        self._position_preview.set_layout(
            self._current_anchor(), self.margin_x.value(), self.margin_y.value())

    def _refresh_preview(self) -> None:
        """Render the HUD thumbnail in the theme the overlay will use."""
        name = str(self._settings.value(OVERRIDE_KEY, "")) or DEFAULT_THEME.name
        if name == self._preview_rendered_for or not self.isVisible():
            return
        # imported here so the main process only pays for QtQuick once the
        # window is actually opened
        from ppeek.overlay.preview import render_theme_preview

        img = render_theme_preview("", theme=THEMES_BY_NAME.get(name, DEFAULT_THEME))
        self._position_preview.set_hud(QPixmap.fromImage(img))
        self._preview_rendered_for = name

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_preview()
