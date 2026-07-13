"""Process wiring.

Main process: config hub UI + SayoDevice HID + tosu supervision.
Overlay process (spawned with --overlay): layer-shell QML HUD + telemetry + evdev.
Split exists because Qt's layer-shell integration is process-global.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_OSU_COMM = "osu!"
_TOSU_COMM = "tosu"
_GAME_WARMUP_S = 8.0  # let lazer map its memory before tosu scans it


def _find_tosu_binary() -> str | None:
    tosu = shutil.which("tosu")
    if tosu:
        return tosu
    if os.access("/opt/tosu/tosu", os.X_OK):
        return "/opt/tosu/tosu"
    return None


def _scan_procs(name: str) -> list[tuple[int, int]]:
    """All (pid, starttime) matching by comm OR argv[0] basename.

    Comm alone is not enough: Bun/Node binaries like tosu report comm
    "MainThread", so we also match the executable name from cmdline.
    starttime is in clock ticks since boot.
    """
    found = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        base = "/proc/" + entry
        try:
            with open(base + "/comm", "rb") as fh:
                comm = fh.read().strip().decode(errors="replace")
            if comm != name:
                with open(base + "/cmdline", "rb") as fh:
                    argv0 = fh.read().split(b"\0", 1)[0].decode(errors="replace")
                if os.path.basename(argv0) != name:
                    continue
            with open(base + "/stat", "rb") as fh:
                stat = fh.read().decode(errors="replace")
            # comm field may contain spaces/parens — split after the closing ')'
            starttime = int(stat.rsplit(")", 1)[1].split()[19])
        except (OSError, ValueError, IndexError):
            continue  # process vanished mid-scan or unreadable
        found.append((int(entry), starttime))
    return found


async def _kill_process(pid: int) -> None:
    """SIGTERM, short grace, then SIGKILL (tosu tends to ignore SIGTERM)."""
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    for _ in range(10):
        await asyncio.sleep(0.1)
        try:
            os.kill(pid, 0)
        except OSError:
            return
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def _spawn_tosu(binary: str) -> None:
    logger.info("starting tosu")
    subprocess.Popen(
        [binary, "--update=false"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


async def _tosu_supervisor() -> None:
    """Keep tosu freshly attached to the running osu! process.

    tosu 4.25 attaches only partially when it predates the game process
    (hitErrorArray flows, pp/combo/acc read as zero), so the invariant is:
    tosu's start time must be NEWER than the game's. Whenever the game
    restarts, kill every tosu and spawn a fresh one.
    """
    binary = _find_tosu_binary()
    if binary is None:
        logger.warning("tosu binary not found — pp telemetry unavailable")
        return
    clk = os.sysconf("SC_CLK_TCK")
    last_spawn = 0.0
    while True:
        try:
            osu = max(_scan_procs(_OSU_COMM), key=lambda p: p[1], default=None)
            tosus = _scan_procs(_TOSU_COMM)
            if osu is not None:
                with open("/proc/uptime") as fh:
                    uptime = float(fh.read().split()[0])
                game_age = uptime - osu[1] / clk
                if game_age >= _GAME_WARMUP_S:
                    stale = [pid for pid, started in tosus if started < osu[1]]
                    if stale:
                        logger.info(
                            "osu! restarted — restarting tosu (stale attach: %s)", stale
                        )
                        for pid, _started in tosus:
                            await _kill_process(pid)
                        tosus = []
                    if not tosus:
                        # rate limit: if a spawned tosu doesn't show up in the
                        # scan (e.g. unexpected comm/argv), don't fork-bomb
                        now = asyncio.get_running_loop().time()
                        if now - last_spawn >= 30.0:
                            last_spawn = now
                            _spawn_tosu(binary)
                        else:
                            logger.warning(
                                "tosu spawned recently but not visible in scan — waiting"
                            )
        except Exception:
            logger.exception("tosu supervisor iteration failed")
        await asyncio.sleep(3.0)


def _spawn_overlay() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", "osusayohub", "--overlay"])


def run() -> None:
    if "--overlay" in sys.argv:
        from osusayohub.overlay.main import run_overlay

        run_overlay()
        return

    import qasync
    from PyQt6.QtCore import QSettings
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    from osusayohub.confighub.window import ConfigHubWindow
    from osusayohub.device.sayodevice import SayoDevice
    from osusayohub.input.tracker import list_keyboards

    app = QApplication(sys.argv)
    app.setApplicationName("OsuSayoHub")
    # closing the config hub window minimizes to tray; Quit lives in the tray menu
    app.setQuitOnLastWindowClosed(False)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    settings = QSettings("osusayohub", "osusayohub")

    overlay_proc = _spawn_overlay()

    device = SayoDevice()
    confighub = ConfigHubWindow(device)
    confighub.show()

    # input-device selector: config hub writes the choice, overlay follows via file watch
    input_combo = confighub.overlay_tab.input_source
    for path, name in list_keyboards():
        input_combo.addItem(f"{name} ({path})", userData=path)
    saved = str(settings.value("input/device_path", ""))
    idx = input_combo.findData(saved)
    if idx >= 0:
        input_combo.setCurrentIndex(idx)

    def on_device_changed(index: int) -> None:
        path = input_combo.itemData(index)
        if path:
            settings.setValue("input/device_path", path)
            settings.sync()

    input_combo.currentIndexChanged.connect(on_device_changed)

    # -- tray icon ------------------------------------------------------

    icon = QIcon.fromTheme("osusayohub")
    if icon.isNull():
        # dev checkout: package not installed, load straight from the repo
        from pathlib import Path

        svg = Path(__file__).parents[2] / "packaging" / "osusayohub.svg"
        icon = QIcon(str(svg))

    def toggle_confighub() -> None:
        if confighub.isVisible():
            confighub.hide()
        else:
            confighub.show()
            confighub.raise_()
            confighub.activateWindow()

    def restart_tosu() -> None:
        # just kill it — the supervisor notices and spawns a fresh one
        for pid, _started in _scan_procs(_TOSU_COMM):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def restart_overlay() -> None:
        nonlocal overlay_proc
        overlay_proc.terminate()
        overlay_proc = _spawn_overlay()

    tray_menu = QMenu()
    tray_menu.addAction("Config Hub", toggle_confighub)
    tray_menu.addSeparator()
    tray_menu.addAction("Restart tosu", restart_tosu)
    tray_menu.addAction("Restart overlay", restart_overlay)
    tray_menu.addSeparator()
    tray_menu.addAction("Quit", app.quit)

    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("OsuSayoHub")
    tray.setContextMenu(tray_menu)

    def on_tray_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            toggle_confighub()

    tray.activated.connect(on_tray_activated)
    tray.show()

    def _shutdown() -> None:
        device.close()
        overlay_proc.terminate()
        for pid, _started in _scan_procs(_TOSU_COMM):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

    app.aboutToQuit.connect(_shutdown)

    with loop:
        supervisor = loop.create_task(_tosu_supervisor())
        loop.run_forever()
        supervisor.cancel()
