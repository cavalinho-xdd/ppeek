"""Process wiring.

Main process: tray icon + settings window + tosu supervision.
Overlay process (spawned with --overlay): HUD + telemetry (+ evdev on Linux).
Split exists because Qt's layer-shell integration is process-global.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil

def _setup_logging() -> None:
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    if getattr(sys, "frozen", False):
        # windowed exe has no stdout/stderr — StreamHandler would silently
        # drop everything, so log to a file per process role instead
        logdir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OsuSayoHub"
        logdir.mkdir(parents=True, exist_ok=True)
        name = "overlay.log" if "--overlay" in sys.argv else "main.log"
        logging.basicConfig(
            level=logging.INFO,
            format=fmt,
            handlers=[logging.FileHandler(logdir / name, encoding="utf-8")],
        )
    else:
        logging.basicConfig(level=logging.INFO, format=fmt)


_setup_logging()
logger = logging.getLogger(__name__)

if sys.platform == "win32":
    _OSU_NAMES = {"osu!.exe"}
    _TOSU_NAMES = {"tosu.exe"}
else:
    _OSU_NAMES = {"osu!"}
    _TOSU_NAMES = {"tosu"}
_GAME_WARMUP_S = 8.0  # let lazer map its memory before tosu scans it

# supervisor states surfaced on the tray icon
STATUS_WAITING = "waiting"      # osu! not running
STATUS_ATTACHING = "attaching"  # osu! up, tosu warming up / restarting
STATUS_RUNNING = "running"      # osu! + fresh tosu both up


def _app_dir() -> Path:
    """Directory next to the executable — where a bundled tosu.exe lives."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parents[2]


def _resource_dir() -> Path:
    """Bundled data files (PyInstaller unpacks them under sys._MEIPASS)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).parents[2]


def _find_tosu_binary() -> str | None:
    exe_name = "tosu.exe" if sys.platform == "win32" else "tosu"
    bundled = _app_dir() / exe_name
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)
    tosu = shutil.which("tosu")
    if tosu:
        return tosu
    if os.access("/opt/tosu/tosu", os.X_OK):
        return "/opt/tosu/tosu"
    return None


def _scan_procs(names: set[str]) -> list[psutil.Process]:
    """All processes matching by name OR argv[0] basename.

    Name alone is not enough: Bun/Node binaries like tosu report their
    process name as "MainThread", so we also match the executable name
    from cmdline.
    """
    found = []
    for proc in psutil.process_iter(["name", "cmdline", "create_time"]):
        try:
            if proc.info["name"] in names:
                found.append(proc)
                continue
            cmdline = proc.info["cmdline"] or []
            if cmdline and os.path.basename(cmdline[0]) in names:
                found.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return found


async def _kill_process(proc: psutil.Process) -> None:
    """terminate(), short grace, then kill() (tosu tends to ignore SIGTERM)."""
    try:
        proc.terminate()
    except psutil.Error:
        return
    for _ in range(10):
        await asyncio.sleep(0.1)
        if not proc.is_running():
            return
    try:
        proc.kill()
    except psutil.Error:
        pass


def _spawn_tosu(binary: str) -> None:
    logger.info("starting tosu")
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        [binary, "--update=false"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )


async def _tosu_supervisor(on_status=None) -> None:
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
    last_spawn = 0.0
    while True:
        status = STATUS_WAITING
        try:
            osus = _scan_procs(_OSU_NAMES)
            osu = max(osus, key=lambda p: p.info["create_time"], default=None)
            tosus = _scan_procs(_TOSU_NAMES)
            if osu is not None:
                status = STATUS_ATTACHING
                game_start = osu.info["create_time"]
                if time.time() - game_start >= _GAME_WARMUP_S:
                    stale = [p for p in tosus if p.info["create_time"] < game_start]
                    if stale:
                        logger.info(
                            "osu! restarted — restarting tosu (stale attach: %s)",
                            [p.pid for p in stale],
                        )
                        for proc in tosus:
                            await _kill_process(proc)
                        tosus = []
                    if tosus:
                        status = STATUS_RUNNING
                    else:
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
        if on_status:
            on_status(status)
        await asyncio.sleep(3.0)


def _spawn_overlay() -> subprocess.Popen:
    if getattr(sys, "frozen", False):
        return subprocess.Popen([sys.executable, "--overlay"])
    return subprocess.Popen([sys.executable, "-m", "osusayohub", "--overlay"])


def _base_icon():
    from PyQt6.QtGui import QIcon

    icon = QIcon.fromTheme("osusayohub")
    if not icon.isNull():
        return icon
    # frozen bundle or dev checkout: load straight from packaged assets
    svg = _resource_dir() / "packaging" / "osusayohub.svg"
    return QIcon(str(svg))


def _status_icon(base, color: str):
    """Base icon with a status dot in the corner (gray/amber/green)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

    pixmap = base.pixmap(64, 64)
    if pixmap.isNull():
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    s = pixmap.width()
    r = s * 0.22
    p.drawEllipse(int(s - 2 * r - 2), int(s - 2 * r - 2), int(2 * r), int(2 * r))
    p.end()
    return QIcon(pixmap)


def run() -> None:
    if "--overlay" in sys.argv:
        from osusayohub.overlay.main import run_overlay

        run_overlay()
        return

    import qasync
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    from osusayohub.confighub.window import SettingsWindow
    from osusayohub.input.tracker import list_keyboards

    app = QApplication(sys.argv)
    app.setApplicationName("OsuSayoHub")
    # closing the settings window minimizes to tray; Quit lives in the tray menu
    app.setQuitOnLastWindowClosed(False)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    settings = QSettings("osusayohub", "osusayohub")

    overlay_proc = _spawn_overlay()

    settings_win = SettingsWindow(settings)
    # first launch: show the window so starting the app visibly does something;
    # afterwards it lives in the tray only
    if not settings.value("app/first_run_done", False, type=bool):
        settings.setValue("app/first_run_done", True)
        settings_win.show()

    # input-device selector (Linux only): settings window writes the choice,
    # overlay follows via file watch
    input_combo = settings_win.input_source
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

    base_icon = _base_icon()
    status_icons = {
        STATUS_WAITING: _status_icon(base_icon, "#808080"),
        STATUS_ATTACHING: _status_icon(base_icon, "#e0a030"),
        STATUS_RUNNING: _status_icon(base_icon, "#40c060"),
    }
    status_tooltips = {
        STATUS_WAITING: "OsuSayoHub — waiting for osu!",
        STATUS_ATTACHING: "OsuSayoHub — attaching tosu…",
        STATUS_RUNNING: "OsuSayoHub — running",
    }

    def toggle_settings() -> None:
        if settings_win.isVisible():
            settings_win.hide()
        else:
            settings_win.show()
            settings_win.raise_()
            settings_win.activateWindow()

    def restart_tosu() -> None:
        # just kill it — the supervisor notices and spawns a fresh one
        for proc in _scan_procs(_TOSU_NAMES):
            try:
                proc.kill()
            except psutil.Error:
                pass

    def restart_overlay() -> None:
        nonlocal overlay_proc
        overlay_proc.terminate()
        overlay_proc = _spawn_overlay()

    tray_menu = QMenu()
    tray_menu.addAction("Settings", toggle_settings)
    tray_menu.addSeparator()
    tray_menu.addAction("Restart tosu", restart_tosu)
    tray_menu.addAction("Restart overlay", restart_overlay)
    tray_menu.addSeparator()
    tray_menu.addAction("Quit", app.quit)

    tray = QSystemTrayIcon(status_icons[STATUS_WAITING], app)
    tray.setToolTip(status_tooltips[STATUS_WAITING])
    tray.setContextMenu(tray_menu)

    last_status = STATUS_WAITING

    def on_status(status: str) -> None:
        nonlocal last_status
        if status == last_status:
            return
        last_status = status
        tray.setIcon(status_icons[status])
        tray.setToolTip(status_tooltips[status])

    def on_tray_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            toggle_settings()

    tray.activated.connect(on_tray_activated)
    tray.show()

    def _shutdown() -> None:
        overlay_proc.terminate()
        for proc in _scan_procs(_TOSU_NAMES):
            try:
                proc.terminate()
            except psutil.Error:
                pass

    app.aboutToQuit.connect(_shutdown)

    with loop:
        supervisor = loop.create_task(_tosu_supervisor(on_status=on_status))
        loop.run_forever()
        supervisor.cancel()
