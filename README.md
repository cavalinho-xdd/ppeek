# osu!SayoHub

**Live PP overlay for [osu!lazer](https://osu.ppy.sh) — hit-error meter, UR, combo, accuracy and KPS, with skin-driven themes. Windows & Linux.**

<p align="center">
  <img src="docs/overlay-arona-plana.png" alt="Arona & Plana pastel theme" width="380">
  &nbsp;&nbsp;
  <img src="docs/overlay-fool-moon-night.png" alt="Fool Moon Night ink theme" width="380">
</p>

<p align="center">
  <em>The overlay re-themes itself to match the skin you're playing —<br>
  Arona &amp; Plana (Blue Archive) pastel on the left, FOOL MOON NIGHT hand-drawn ink on the right.</em>
</p>

---

## ✨ Features

- **Live PP**, combo, accuracy, grade and hit counts — streamed from [tosu](https://tosu.app) over its local WebSocket, no osu! plugins needed
- **Hit-error meter** with fading tick marks and 300/100/50 windows, plus **UR (unstable rate)** readout
- **KPS counter** — evdev on Linux, tosu keyOverlay counters on Windows
- **Click-through & focus-free** — the overlay never steals input from the game
- **Auto-hide**: appears when a beatmap starts, disappears after it ends
- **Tray status icon**: gray = waiting for osu!, amber = attaching tosu, green = running
- **tosu is managed for you** — the app starts and restarts tosu automatically, no manual setup

### 🎨 Skin-driven themes
The overlay reads the **active skin name from osu!lazer** (via tosu) and switches its entire look on the fly:

| Skin | Theme |
|---|---|
| FOOL MOON NIGHT | Hand-drawn monochrome ink: hatched planets, crescent moon, twinkling stars, water ripples, Gaegu font |
| Arona & Plana (HK7205A) | Blue Archive pastel: red halo with its trailing string, stripe clusters, drifting diamonds, Readex Pro font — colors sampled from the skin's own `skin.ini` |
| anything else | Falls back to the ink theme |

Everything is painted procedurally — no image assets, just code. Adding a theme for your skin is a single palette entry in [`osusayohub/overlay/theme.py`](osusayohub/overlay/theme.py).

## 🚀 Getting started

### Windows 10 / 11

1. Download `OsuSayoHub-windows.zip` from the [latest release](../../releases/latest)
2. Unzip anywhere and run `OsuSayoHub.exe` (tosu is bundled and started automatically)
3. Start osu!lazer in **borderless / windowed fullscreen** — no overlay software can draw over exclusive fullscreen
4. The tray icon turns green when everything is attached; the overlay appears when you start a beatmap

### Arch Linux
```sh
git clone https://github.com/cavalinho-xdd/osusayohub.git
cd osusayohub
makepkg -si
```

On Wayland with `layer-shell-qt` the overlay renders on the wlr-layer-shell overlay layer (visible above fullscreen games); X11 falls back to a frameless always-on-top window.

### Anywhere else
```sh
pip install .
osusayohub
```

## 🧩 How it works

```
osu!lazer ──▶ tosu ──▶ WebSocket (localhost:24050) ──▶ telemetry listener
                                                          │
     evdev (Linux) / keyOverlay ──▶ KPS + UR fallback ────┤
                                                          ▼
                                       Qt overlay (layer-shell / widget)
                                                 theme ⇆ active skin
```

- Single asyncio loop inside the Qt main loop (qasync) — no threads
- A supervisor keeps tosu freshly attached: whenever osu! restarts, tosu is restarted too
- Telemetry UR wins; evdev rhythm-stability UR only fills the gaps

## 🗺️ Roadmap

- [x] Windows port
- [ ] More skin themes
- [ ] Theme editor

## 📄 License

MIT. Bundled fonts ([Gaegu](https://fonts.google.com/specimen/Gaegu), [Readex Pro](https://fonts.google.com/specimen/Readex+Pro)) are licensed under the SIL Open Font License.
