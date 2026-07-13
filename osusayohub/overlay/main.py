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

    from osusayohub.input.tracker import (
        ClickTracker,
        calculate_unstable_rate,
        evdev_available,
    )
    from osusayohub.osu.telemetry import PreciseListener, TelemetryListener

    app = QApplication(sys.argv)
    app.setApplicationName("osusayohub-overlay")
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    settings = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "osusayohub", "osusayohub")

    from osusayohub.overlay.bridge import HubState

    hub = HubState()

    window = None

    def read_layout() -> None:
        settings.sync()
        anchor = str(settings.value("overlay/anchor", "bottom-right"))
        mx = int(settings.value("overlay/margin_x", 24))
        my = int(settings.value("overlay/margin_y", 24))
        ah = settings.value("overlay/auto_hide", True, type=bool)
        
        logger.info("layout: anchor=%s mx=%s my=%s", anchor, mx, my)
        hub.apply_layout(anchor_name=anchor, margin_x=mx, margin_y=my, auto_hide=ah)
        if window is not None:
            window.apply_layout(anchor_name=anchor, margin_x=mx, margin_y=my, auto_hide=ah)

    read_layout()
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
        read_layout()
        window.show()

    # -- data feeds ------------------------------------------------------

    tracker_holder: dict = {"tracker": None}

    def make_tracker(path: str | None) -> ClickTracker:
        tracker = ClickTracker(device_path=path or None)
        tracker.on_press = lambda _ts: hub.on_fallback_ur(
            calculate_unstable_rate(tracker.timestamps)
        )
        return tracker

    # keyOverlay KPS: sliding window of (time, cumulative press count) samples;
    # used when no evdev tracker runs (Windows) — evdev is more precise
    from collections import deque
    from time import monotonic

    key_samples: deque[tuple[float, int]] = deque()

    def keyoverlay_kps(window_s: float = 1.0) -> float:
        now = monotonic()
        while key_samples and now - key_samples[0][0] > window_s + 0.5:
            key_samples.popleft()
        if len(key_samples) < 2:
            return 0.0
        newest_t, newest_total = key_samples[-1]
        if now - newest_t > window_s:
            return 0.0  # telemetry stalled — don't freeze a stale value
        for t, total in key_samples:
            if newest_t - t <= window_s:
                return max(0, newest_total - total) / window_s
        return 0.0

    def record_key_total(total: int) -> None:
        if total <= 0:
            return
        # a new play resets tosu's counters; drop the old ramp
        if key_samples and total < key_samples[-1][1]:
            key_samples.clear()
        key_samples.append((monotonic(), total))

    def on_frame(frame) -> None:
        # gosumemory-style payloads carry keyOverlay inline; tosu v2 sends
        # it on the /precise endpoint instead (PreciseListener below)
        record_key_total(frame.key_total)
        hub.on_telemetry_frame(frame)
        if window is not None:
            window.on_telemetry_frame(frame)

    def on_disconnect() -> None:
        hub.on_telemetry_disconnect()
        if window is not None:
            window.on_telemetry_disconnect()

    telemetry = TelemetryListener(on_frame=on_frame, on_disconnect=on_disconnect)
    # no evdev (Windows): pull press counters from tosu's precise endpoint
    precise = None
    if not evdev_available():
        precise = PreciseListener(on_key_total=record_key_total)

    def restart_tracker() -> None:
        if not evdev_available():
            return  # Windows/macOS: KPS comes from tosu keyOverlay instead
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

    def push_kps() -> None:
        tracker = tracker_holder["tracker"]
        kps = tracker.keys_per_second() if tracker else keyoverlay_kps()
        hub.on_kps(kps)
        if window is not None:
            window.on_kps(kps)

    kps_timer = QTimer()
    kps_timer.setInterval(250)
    kps_timer.timeout.connect(push_kps)
    kps_timer.start()

    with loop:
        restart_tracker()
        telemetry.start()
        if precise is not None:
            precise.start()
        loop.run_forever()
