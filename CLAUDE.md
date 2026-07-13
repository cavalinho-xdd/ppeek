# OsuSayoHub — Python/PyQt6 Desktop Overlay

All-in-one utility for osu!lazer (live PP, UR visualization) and SayoDevice O3C keypad config.

## Tech Stack

- **Python 3.11+** — no f-strings in formal code (session writes normal code, not caveman)
- **PyQt6** — GUI framework; must use exact Qt window flags for Wayland overlay (see below)
- **qasync** — single asyncio event loop inside PyQt6 main loop (no threads; websocket + evdev run as async tasks)
- **websockets** — osu!lazer local JSON telemetry listener (`localhost:24050/ws`)
- **evdev** — read-only input monitoring; fallback dummy hook when device unavailable (dev machines, CI)
- **hidapi** — write-only USB HID config channel (separate from input/tracker.py by design)

## Wayland (Hyprland) Overlay Constraints

Transparent, always-on-top overlay must not steal focus. Qt flags required:
- `FramelessWindowHint | WindowStaysOnTopHint | Tool` — frameless, stay-on-top, treat as tool window
- `WindowDoesNotAcceptFocus | WA_ShowWithoutActivating` — never accept input focus
- `WA_TranslucentBackground | WA_TransparentForMouseEvents` — transparent bg, pass all clicks through

## Unstable Rate (UR) — dual source

- **Primary**: telemetry `hitErrorArray` / `unstableRate` from tosu (true osu! UR). Feeds overlay hit-error meter.
- **Fallback**: `input/tracker.py:calculate_unstable_rate()` — rhythm-stability stddev of click intervals, rejects gaps >400 ms (breaks/menus). Used only when telemetry UR absent.
- Overlay resolves precedence in `on_unstable_rate()` / `on_telemetry_frame()`.

## SayoDevice O3C Protocol (verified on hardware)

VID 0x8089, PID 0x0009. Config channel = HID interface with **usage page 0xFF00**
(open by path! bare VID/PID open grabs the keyboard interface). Protocol v1,
64-byte output/input reports (NOT feature reports):

- Wire: `[report_id=0x02, cmd, data_len, payload..., checksum]`, checksum = sum & 0xFF
- Response: `[report_id, status, data_len, payload...]` — status 0 = OK, 255 = unsupported cmd
- cmd 0x00 = info (send h/m/s/wday, get fw version + model), 0x04 = save to flash (magic 0x72 0x96),
  0x06 = simple key (bindings — the one O3C supports; cmd 0x16 returns 255),
  0x10 = light (bytes 5/6/7 = R/G/B, verified), 0x11 = palette, 0x08 = device name
- Simple key payload: `pattern|number|type|retain|modifier|kc1|kc2|kc3` (HID usages, kc1 = primary)
- Writes go to device RAM; `save_to_flash()` persists. RT/actuation: O3C has no analog sensing — unsupported.
- Implementation: `device/protocol.py` (wire), `device/sayodevice.py` (facade), `device/hid_usage.py` (Qt↔HID map)
- Sources: Sayobot/Sayo_CLI o2_protocol.cpp, khang06 O3C internals gist

## Architecture

- `osusayohub/core/app.py` — qasync wiring, Qt window setup, task lifecycle
- `osusayohub/osu/telemetry.py` — WebSocket listener, auto-reconnect, TelemetryFrame dataclass
- `osusayohub/overlay/window.py` — transparent PyQt6 widget, PP/UR/combo display
- `osusayohub/input/tracker.py` — evdev hook (read-only), click deque, UR calc
- `osusayohub/device/sayodevice.py` — hidapi write-only channel, feature-report send/recv
- `osusayohub/confighub/window.py` — config UI (RT, key bindings, RGB tabs)

Isolation: input and device modules never cross. Telemetry data flows to overlay only.
