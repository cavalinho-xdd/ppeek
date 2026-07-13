"""Overlay process entry point.

Runs as a dedicated process so QT_WAYLAND_SHELL_INTEGRATION=layer-shell only
affects the HUD window (layer-shell integration is process-global in Qt).
Falls back to the legacy QWidget overlay when layer-shell is unavailable.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_LAYER_SHELL_PLUGIN = Path("/usr/lib/qt6/plugins/wayland-shell-integration/liblayer-shell.so")


def layer_shell_available() -> bool:
    return (
        os.environ.get("XDG_SESSION_TYPE", "") == "wayland"
        or os.environ.get("WAYLAND_DISPLAY")
    ) and _LAYER_SHELL_PLUGIN.exists()


def run_overlay() -> None:
    use_layer_shell = layer_shell_available()
    if use_layer_shell:
        os.environ["QT_WAYLAND_SHELL_INTEGRATION"] = "layer-shell"

    import qasync
    from PyQt6.QtCore import QFileSystemWatcher, QSettings, QTimer
    from PyQt6.QtWidgets import QApplication

    from osusayohub.input.tracker import ClickTracker, calculate_unstable_rate
    from osusayohub.osu.telemetry import TelemetryListener

    app = QApplication(sys.argv)
    app.setApplicationName("osusayohub-overlay")
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    settings = QSettings("osusayohub", "osusayohub")

    from osusayohub.overlay.bridge import HubState

    hub = HubState()

    def read_layout() -> None:
        settings.sync()
        logger.info("layout: anchor=%s mx=%s my=%s",
                    settings.value("overlay/anchor"), settings.value("overlay/margin_x"),
                    settings.value("overlay/margin_y"))
        hub.apply_layout(
            anchor_name=str(settings.value("overlay/anchor", "bottom-right")),
            margin_x=int(settings.value("overlay/margin_x", 24)),
            margin_y=int(settings.value("overlay/margin_y", 24)),
            auto_hide=settings.value("overlay/auto_hide", True, type=bool),
        )

    read_layout()

    window = None
    if use_layer_shell:
        from PyQt6.QtQml import QQmlApplicationEngine

        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("hub", hub)
        qml = Path(__file__).with_name("Overlay.qml")
        engine.load(str(qml))
        if not engine.rootObjects():
            logger.error("QML overlay failed to load, falling back to widget")
            use_layer_shell = False
    if not use_layer_shell:
        from osusayohub.overlay.window import OverlayWindow

        window = OverlayWindow(auto_hide=settings.value("overlay/auto_hide", True, type=bool))
        window.show()

    # -- data feeds ------------------------------------------------------

    tracker_holder: dict = {"tracker": None}

    def make_tracker(path: str | None) -> ClickTracker:
        tracker = ClickTracker(device_path=path or None)
        tracker.on_press = lambda _ts: hub.on_fallback_ur(
            calculate_unstable_rate(tracker.timestamps)
        )
        return tracker

    def on_frame(frame) -> None:
        hub.on_telemetry_frame(frame)
        if window is not None:
            window.on_telemetry_frame(frame)

    def on_disconnect() -> None:
        hub.on_telemetry_disconnect()
        if window is not None:
            window.on_telemetry_disconnect()

    telemetry = TelemetryListener(on_frame=on_frame, on_disconnect=on_disconnect)

    def restart_tracker() -> None:
        if tracker_holder["tracker"]:
            tracker_holder["tracker"].stop()
        tracker = make_tracker(str(settings.value("input/device_path", "")))
        tracker_holder["tracker"] = tracker
        tracker.start()

    # live settings reload (config hub writes, we follow)
    watcher = QFileSystemWatcher()
    settings_file = settings.fileName()
    if Path(settings_file).exists():
        watcher.addPath(settings_file)

    def on_settings_changed(_path: str) -> None:
        old_device = str(settings.value("input/device_path", ""))
        read_layout()
        new_device = str(settings.value("input/device_path", ""))
        if new_device != old_device:
            restart_tracker()
        # QSettings may replace the file; re-arm the watcher
        if settings_file not in watcher.files() and Path(settings_file).exists():
            watcher.addPath(settings_file)

    watcher.fileChanged.connect(on_settings_changed)

    kps_timer = QTimer()
    kps_timer.setInterval(250)
    kps_timer.timeout.connect(
        lambda: hub.on_kps(
            tracker_holder["tracker"].keys_per_second() if tracker_holder["tracker"] else 0.0
        )
    )
    kps_timer.start()

    with loop:
        restart_tracker()
        telemetry.start()
        loop.run_forever()
