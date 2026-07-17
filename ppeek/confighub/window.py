"""Settings window: overlay position/behavior, input source, skin showcase.

The General tab uses native Qt widgets only (no stylesheets) so it
follows the user's system Qt theme. Writes settings; the overlay process
watches the settings file and applies changes live. The Skins tab
(confighub.skins) is intentionally custom-painted.
"""
from __future__ import annotations

import sys

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ppeek.confighub.skins import SkinShowcase

ANCHOR_LABELS = [
    ("Top left", "top-left"),
    ("Top center", "top-center"),
    ("Top right", "top-right"),
    ("Bottom left", "bottom-left"),
    ("Bottom center", "bottom-center"),
    ("Bottom right", "bottom-right"),
]


class SettingsWindow(QWidget):
    def __init__(self, settings: QSettings):
        super().__init__()
        self.setWindowTitle("PPeek Settings")
        self.resize(720, 560)
        self._settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        general = QWidget()
        form = QFormLayout(general)

        self.auto_hide = QCheckBox("Show only during gameplay")
        self.auto_hide.setChecked(settings.value("overlay/auto_hide", True, type=bool))
        self.auto_hide.toggled.connect(self._save)
        form.addRow(self.auto_hide)

        self.anchor = QComboBox()
        saved_anchor = str(settings.value("overlay/anchor", "bottom-right"))
        for label, value in ANCHOR_LABELS:
            self.anchor.addItem(label, userData=value)
        idx = self.anchor.findData(saved_anchor)
        if idx >= 0:
            self.anchor.setCurrentIndex(idx)
        self.anchor.currentIndexChanged.connect(self._save)
        form.addRow("Screen corner", self.anchor)

        self.margin_x = QSpinBox()
        self.margin_x.setRange(0, 4000)
        self.margin_x.setValue(int(settings.value("overlay/margin_x", 24)))
        self.margin_x.valueChanged.connect(self._save)
        form.addRow("Horizontal offset", self.margin_x)

        self.margin_y = QSpinBox()
        self.margin_y.setRange(0, 4000)
        self.margin_y.setValue(int(settings.value("overlay/margin_y", 24)))
        self.margin_y.valueChanged.connect(self._save)
        form.addRow("Vertical offset", self.margin_y)

        # evdev input source exists only on Linux; elsewhere KPS comes from
        # tosu's keyOverlay counters and there is nothing to pick
        self.input_source = QComboBox()
        if sys.platform == "linux":
            form.addRow("Input device", self.input_source)
        else:
            self.input_source.hide()

        if sys.platform == "win32":
            hint = QLabel(
                "Run osu!lazer in borderless / windowed fullscreen —\n"
                "no overlay can draw over exclusive fullscreen.\n"
                "Changes apply live."
            )
        else:
            hint = QLabel(
                "Overlay renders on the wlr-layer-shell overlay layer —\n"
                "visible above fullscreen games. Changes apply live."
            )
        hint.setWordWrap(True)
        form.addRow(hint)

        tabs.addTab(general, "General")
        tabs.addTab(SkinShowcase(settings), "Skins")

    def _save(self, *_args) -> None:
        self._settings.setValue("overlay/auto_hide", self.auto_hide.isChecked())
        self._settings.setValue("overlay/anchor", self.anchor.currentData())
        self._settings.setValue("overlay/margin_x", self.margin_x.value())
        self._settings.setValue("overlay/margin_y", self.margin_y.value())
        self._settings.sync()
