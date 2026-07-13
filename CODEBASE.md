# OsuOverlay — Codebase Guide

Single source of truth for how this project is built, how it works, and how to
extend it. If you read only one document, read this one.

---

## 1. What this is

Desktop companion for **osu!lazer**, currently focused on:

1. **Gameplay overlay** — transparent, click-through, always-on-top HUD showing
   live PP, combo, accuracy, grade, hit counts, a hit-error meter, UR
   (unstable rate) and KPS. Re-themes itself based on the osu! skin you play.

Built for Wayland/Hyprland (layer-shell), but degrades gracefully to X11 and Windows via QWidget fallback.

---

## 2. Tech stack & dependencies

### Runtime dependencies (`pyproject.toml` / PKGBUILD `depends`)

| Package | Why | Where used |
|---|---|---|
| Python ≥ 3.11 | `slots=True` dataclasses, modern typing | everywhere |
| **PyQt6** | GUI: widgets (fallback overlay), QML (main overlay), QSettings | `overlay/` |
| **qasync** | runs one asyncio event loop *inside* the Qt main loop | `core/app.py`, `overlay/main.py` |
| **websockets** | client for tosu's local WebSocket telemetry | `osu/telemetry.py` |
| **evdev** | read-only keyboard monitoring (Linux KPS/UR). Optional — degrades to tosu's precise endpoint on Windows | `input/tracker.py` |
| **qt6-declarative** | QML engine for the layer-shell overlay | `overlay/Overlay.qml` |
| **layer-shell-qt** | wlr-layer-shell integration → true overlay surface on Wayland | `overlay/main.py`, `Overlay.qml` |

### External runtime tools (not Python)

| Tool | Role |
|---|---|
| **osu!lazer** | the game. Telemetry is read from its memory by tosu, not by us |
| **[tosu](https://tosu.app)** | memory reader exposing game state as JSON. We supervise/restart it |

### Build/packaging

`python-build`, `python-installer`, `python-wheel`, `python-setuptools`.

### Bundled assets

- `osusayohub/assets/fonts/` — **Gaegu** and **Readex Pro**.

---

## 3. Repository map

```text
osusayohub/                     Python package (the app)
├── __main__.py                 `python -m osusayohub` → core.app.run()
├── core/
│   └── app.py                  MAIN PROCESS: qasync wiring, tray icon,
│                               tosu supervisor, spawns the overlay process
├── osu/
│   └── telemetry.py            tosu WebSocket listener, TelemetryFrame, GameState
├── overlay/
│   ├── main.py                 OVERLAY PROCESS entry: picks QML vs widget path
│   ├── Overlay.qml             primary HUD (Wayland layer-shell), all 3 themes
│   ├── bridge.py               HubState — QObject exposing frame/theme to QML
│   ├── window.py               fallback HUD (QWidget, QPainter), all 3 themes
│   └── theme.py                OverlayTheme palettes, skin-name → theme matching
├── input/
│   └── tracker.py              evdev read-only click tracker, KPS, rhythm UR
└── assets/fonts/               bundled OFL fonts

main.py                         dev convenience launcher
tests/                          empty scaffold
packaging/                      .desktop, tray/app icon SVG, udev rules
PKGBUILD                        Arch package
pyproject.toml                  setuptools config
README.md                       project description
CODEBASE.md                     this file
```

---

## 4. Process architecture

**Two processes.** Qt's layer-shell integration is *process-global*.

```text
main process (core/app.py)                overlay process (overlay/main.py)
─────────────────────────────             ────────────────────────────────────
QApplication + qasync loop                QApplication + qasync loop
system tray (toggle/restart/quit)         layer-shell? ── yes → QML Overlay.qml
tosu supervisor (async task)              │                no → QWidget OverlayWindow
  └─ spawns overlay via                   telemetry listener (osu/telemetry.py)
     `python -m osusayohub --overlay`     evdev ClickTracker (input/tracker.py)
```

**tosu supervisor** (`core/app.py::_tosu_supervisor`): every 3 s scan `/proc`. Ensures tosu started after osu!.

---

## 5. Telemetry (`osu/telemetry.py`)

- `TelemetryListener` — reconnecting client for tosu v2 API.
- Drives auto-show/hide, stats, error meter, and theming.

### UR Precedence

1. telemetry `unstableRate` (always wins when > 0)
2. `input/tracker.py` rhythm UR fallback.

---

## 6. Overlay — two implementations, one contract

Both consume the same inputs.

### Primary: QML + layer-shell (`Overlay.qml` + `bridge.py`)
- Used on Wayland with layer-shell plugin. `HubState` bridges data.

### Fallback: QWidget (`window.py`)
- Painted with QPainter at 30 fps. Used on X11 and **Windows**.
- Uses `FramelessWindowHint | WindowStaysOnTopHint | Tool` and transparent background.

---

## 7. Theme system

Themes live in **`osusayohub/overlay/theme.py`**.
Matches `settings.skin.name` via case-insensitive substring.

| Theme | Trigger substring | Scene | Visual style |
|---|---|---|---|
| `FULL_MOON_NIGHT` | `"fool moon night"` | `night` | Hand-drawn monochrome ink on night sky: hatched planets, crescent moon, twinkling stars, water ripples |
| `ARONA_PLANA` | `"hk7205"` / `"アロナ"` | `pastel` | Blue Archive motifs: pastel blue on navy, tilted red halo, stripe clusters, dot grids, drifting hollow squares |
| `FREEDOM_DIVE` | `"freedom dive"` | `freedom` | Cosmic scene from BTMC × Spoo skin by @tofumang_: cute blob planets with rainbow rings and faces (>w<, ˆ_ˆ, ._o), shooting star arrows, white diamond confetti, golden sparkle stars |

Each theme defines: `ink`, `body_fill`, `miss`, `bg_top`, `bg_bottom`, `accent`, `deco_red`, `font`.

Both `Overlay.qml` (QML Canvas) and `window.py` (QPainter) implement all three scenes with identical visual output.

---

## 8. Windows Compatibility

The overlay is fully compatible with Windows via built-in fallbacks:
- **Display**: Wayland `layer-shell` is missing on Windows, triggering the `QWidget` fallback (`OverlayWindow`). Qt's `WindowStaysOnTopHint` provides native overlay capabilities on Windows.
- **Input tracking**: Linux `evdev` fails, but `main.py` catches this (`evdev_available()`) and falls back to pulling KPS from tosu's `/precise` websocket endpoint (`PreciseListener`).
- **Supervision**: Process scanning (`/proc` in `core/app.py`) is Linux-only. Windows requires bypassing the supervisor or porting it to `psutil`.
