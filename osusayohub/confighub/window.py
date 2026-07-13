"""Configuration Hub: key bindings, RGB, device info, overlay position.

Native Qt widgets only (no stylesheets) so the window follows the user's
system Qt theme (Hyprland dotfiles).
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from osusayohub.device.sayodevice import SayoDevice, SayoDeviceError

logger = logging.getLogger(__name__)

KEY_COUNT = 3  # O3C: three main keys


class KeyBindingsTab(QWidget):
    """Reads current bindings from the device; writes go to device RAM,
    'Save to flash' makes them survive replug."""

    def __init__(self, device: SayoDevice):
        super().__init__()
        self._device = device
        self._editors: list[QKeySequenceEdit] = []
        self._numbers: list[int] = []

        self._grid = QGridLayout()

        self.apply_btn = QPushButton("Apply (device RAM)")
        self.apply_btn.clicked.connect(self._apply)
        self.save_btn = QPushButton("Save to flash")
        self.save_btn.setToolTip("Persist current device config — survives unplug")
        self.save_btn.clicked.connect(self._save_flash)

        layout = QVBoxLayout(self)
        layout.addLayout(self._grid)
        layout.addStretch(1)
        layout.addWidget(self.apply_btn)
        layout.addWidget(self.save_btn)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.load_from_device()

    def load_from_device(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._editors.clear()
        self._numbers.clear()

        if not self._device.is_open:
            self.status.setText("Device not connected.")
            return
        try:
            bindings = self._device.read_bindings()
        except SayoDeviceError as exc:
            self.status.setText(f"Failed to read bindings: {exc}")
            return

        for row, binding in enumerate(bindings):
            self._grid.addWidget(QLabel(f"Key {binding.number + 1}"), row, 0)
            editor = QKeySequenceEdit()
            editor.setMaximumSequenceLength(1)
            if binding.qt_key:
                editor.setKeySequence(binding.display())
            self._editors.append(editor)
            self._numbers.append(binding.number)
            self._grid.addWidget(editor, row, 1)
        self.status.setText(f"Loaded {len(bindings)} bindings from device.")

    def _apply(self) -> None:
        applied = 0
        for editor, number in zip(self._editors, self._numbers):
            seq = editor.keySequence()
            if seq.isEmpty():
                continue
            qt_key = seq[0].key().value
            try:
                self._device.set_key_binding(number, qt_key)
                applied += 1
            except SayoDeviceError as exc:
                self.status.setText(f"Key {number + 1}: {exc}")
                return
        self.status.setText(
            f"Applied {applied} bindings to device RAM. Use 'Save to flash' to persist."
        )

    def _save_flash(self) -> None:
        try:
            self._device.save_to_flash()
            self.status.setText("Saved to flash — config survives replug.")
        except SayoDeviceError as exc:
            self.status.setText(f"Save failed: {exc}")


class RgbTab(QWidget):
    def __init__(self, device: SayoDevice, settings: QSettings):
        super().__init__()
        self._device = device
        self._settings = settings
        self._colors: list[QColor] = []
        self._swatches: list[QPushButton] = []

        grid = QGridLayout()
        for i in range(KEY_COUNT):
            grid.addWidget(QLabel(f"Key {i + 1}"), i, 0)
            color = QColor(settings.value(f"rgb/key{i}", "#04fa00"))
            self._colors.append(color)
            swatch = QPushButton()
            swatch.setFixedSize(48, 24)
            swatch.clicked.connect(lambda _=False, idx=i: self._pick(idx))
            self._swatches.append(swatch)
            self._refresh_swatch(i)
            grid.addWidget(swatch, i, 1)

        self.sync_check = QCheckBox("Same color for all keys")
        self.sync_check.setChecked(settings.value("rgb/sync", True, type=bool))

        apply_btn = QPushButton("Apply (device RAM)")
        apply_btn.clicked.connect(self._apply)
        save_btn = QPushButton("Save to flash")
        save_btn.clicked.connect(self._save_flash)

        layout = QVBoxLayout(self)
        layout.addLayout(grid)
        layout.addWidget(self.sync_check)
        layout.addStretch(1)
        layout.addWidget(apply_btn)
        layout.addWidget(save_btn)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def _refresh_swatch(self, idx: int) -> None:
        # single styled property; swatch color has no theme equivalent
        self._swatches[idx].setStyleSheet(f"background-color: {self._colors[idx].name()};")

    def _pick(self, idx: int) -> None:
        color = QColorDialog.getColor(self._colors[idx], self, f"Key {idx + 1} color")
        if not color.isValid():
            return
        targets = range(KEY_COUNT) if self.sync_check.isChecked() else [idx]
        for i in targets:
            self._colors[i] = color
            self._refresh_swatch(i)

    def _apply(self) -> None:
        self._settings.setValue("rgb/sync", self.sync_check.isChecked())
        for i, color in enumerate(self._colors):
            self._settings.setValue(f"rgb/key{i}", color.name())
            try:
                self._device.set_rgb(i, color.red(), color.green(), color.blue())
            except SayoDeviceError as exc:
                self.status.setText(f"Key {i + 1}: {exc}")
                return
        self.status.setText("Colors applied to device RAM. Use 'Save to flash' to persist.")

    def _save_flash(self) -> None:
        try:
            self._device.save_to_flash()
            self.status.setText("Saved to flash.")
        except SayoDeviceError as exc:
            self.status.setText(f"Save failed: {exc}")


class DeviceTab(QWidget):
    """Model / firmware info, device rename, flash save."""

    def __init__(self, device: SayoDevice):
        super().__init__()
        self._device = device

        info_group = QGroupBox("Device")
        form = QFormLayout(info_group)
        self.model_label = QLabel("—")
        self.fw_label = QLabel("—")
        form.addRow("Model", self.model_label)
        form.addRow("Firmware", self.fw_label)

        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(58)
        rename_btn = QPushButton("Rename device")
        rename_btn.clicked.connect(self._rename)
        form.addRow("Name", self.name_edit)
        form.addRow(rename_btn)

        save_btn = QPushButton("Save all settings to flash")
        save_btn.clicked.connect(self._save_flash)

        note = QLabel(
            "Rapid trigger / actuation: not supported by O3C firmware "
            "(mechanical switches, no analog sensing)."
        )
        note.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(info_group)
        layout.addWidget(note)
        layout.addStretch(1)
        layout.addWidget(save_btn)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.load_from_device()

    def load_from_device(self) -> None:
        info = self._device.info
        if info is None:
            self.model_label.setText("—")
            self.fw_label.setText("—")
            return
        self.model_label.setText(self._device.description())
        self.fw_label.setText(info.firmware_version)
        self.name_edit.setText(self._device.device_name())

    def _rename(self) -> None:
        try:
            self._device.set_device_name(self.name_edit.text())
            self.status.setText("Name written to device RAM — save to flash to persist.")
        except SayoDeviceError as exc:
            self.status.setText(f"Rename failed: {exc}")

    def _save_flash(self) -> None:
        try:
            self._device.save_to_flash()
            self.status.setText("Saved to flash.")
        except SayoDeviceError as exc:
            self.status.setText(f"Save failed: {exc}")


ANCHOR_LABELS = [
    ("Top left", "top-left"),
    ("Top center", "top-center"),
    ("Top right", "top-right"),
    ("Bottom left", "bottom-left"),
    ("Bottom center", "bottom-center"),
    ("Bottom right", "bottom-right"),
]


class OverlayTab(QWidget):
    """Overlay behavior + position. Writes settings; the overlay process
    watches the settings file and applies changes live."""

    def __init__(self, settings: QSettings):
        super().__init__()
        self._settings = settings

        form = QFormLayout(self)

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

        self.input_source = QComboBox()
        form.addRow("Input device", self.input_source)

        hint = QLabel("Overlay renders on the wlr-layer-shell overlay layer —\nvisible above fullscreen games. Changes apply live.")
        hint.setWordWrap(True)
        form.addRow(hint)

    def _save(self, *_args) -> None:
        self._settings.setValue("overlay/auto_hide", self.auto_hide.isChecked())
        self._settings.setValue("overlay/anchor", self.anchor.currentData())
        self._settings.setValue("overlay/margin_x", self.margin_x.value())
        self._settings.setValue("overlay/margin_y", self.margin_y.value())
        self._settings.sync()


class ConfigHubWindow(QWidget):
    def __init__(self, device: SayoDevice):
        super().__init__()
        self.setWindowTitle("OsuSayoHub")
        self.resize(520, 420)

        self._device = device
        self._settings = QSettings("osusayohub", "osusayohub")

        # connect before building tabs so they can read initial state
        try:
            self._device.open()
        except SayoDeviceError as exc:
            logger.info("device not connected at startup: %s", exc)

        tabs = QTabWidget()
        self.bindings_tab = KeyBindingsTab(device)
        tabs.addTab(self.bindings_tab, "Key Bindings")
        self.rgb_tab = RgbTab(device, self._settings)
        tabs.addTab(self.rgb_tab, "RGB")
        self.device_tab = DeviceTab(device)
        tabs.addTab(self.device_tab, "Device")
        self.overlay_tab = OverlayTab(self._settings)
        tabs.addTab(self.overlay_tab, "Overlay")

        self._status = QStatusBar()
        self._reconnect_btn = QPushButton("Reconnect")
        self._reconnect_btn.clicked.connect(self.refresh_device)
        self._status.addPermanentWidget(self._reconnect_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(self._status)

        self._update_status()

    def refresh_device(self) -> None:
        try:
            self._device.close()
            self._device.open()
        except SayoDeviceError as exc:
            self._status.showMessage(f"Device not connected — {exc}")
            return
        self.bindings_tab.load_from_device()
        self.device_tab.load_from_device()
        self._update_status()

    def _update_status(self) -> None:
        if self._device.is_open:
            self._status.showMessage(f"Connected: {self._device.description()}")
        else:
            self._status.showMessage("Device not connected")

    @property
    def settings(self) -> QSettings:
        return self._settings
