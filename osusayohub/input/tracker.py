"""Raw evdev input hook: read-only monitoring for click timing / UR / KPS."""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Callable

logger = logging.getLogger(__name__)

try:
    import evdev  # Linux only; absent on Windows/macOS builds
except ImportError:
    evdev = None


def evdev_available() -> bool:
    return evdev is not None


def list_keyboards() -> list[tuple[str, str]]:
    """Return (path, name) for every readable device that emits key events."""
    if evdev is None:
        return []
    found = []
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except (OSError, PermissionError):
            continue
        caps = dev.capabilities()
        if evdev.ecodes.EV_KEY in caps:
            found.append((path, dev.name))
        dev.close()
    return found


class ClickTracker:
    """Watches a keyboard/keypad device node for key-down events.

    Read-only: never writes to the device. Feeds raw press timestamps
    (microsecond resolution, evdev clock) into a ring buffer for
    Unstable Rate and keys-per-second calculation.
    """

    def __init__(
        self,
        device_path: str | None = None,
        history: int = 512,
        watch_keys: set[int] | None = None,
        on_press: Callable[[float], None] | None = None,
    ):
        self._device_path = device_path
        self._watch_keys = watch_keys  # None = all keys
        self.on_press = on_press
        self._timestamps: deque[float] = deque(maxlen=history)
        self._task: asyncio.Task | None = None

    @property
    def timestamps(self) -> deque[float]:
        return self._timestamps

    def keys_per_second(self, window: float = 1.0) -> float:
        if not self._timestamps:
            return 0.0
        newest = self._timestamps[-1]
        count = sum(1 for t in self._timestamps if newest - t <= window)
        return count / window

    def start(self) -> None:
        self._task = asyncio.ensure_future(self._run())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()

    def _record(self, ts: float) -> None:
        self._timestamps.append(ts)
        if self.on_press:
            self.on_press(ts)

    async def _run(self) -> None:
        if evdev is None or self._device_path is None:
            logger.warning("evdev unavailable or no device selected — dummy hook active")
            await self._run_dummy()
            return

        while True:
            try:
                device = evdev.InputDevice(self._device_path)
                logger.info("tracking input on %s (%s)", self._device_path, device.name)
                async for event in device.async_read_loop():
                    if event.type != evdev.ecodes.EV_KEY or event.value != 1:
                        continue
                    if self._watch_keys and event.code not in self._watch_keys:
                        continue
                    self._record(event.sec + event.usec / 1_000_000)
            except (OSError, PermissionError) as exc:
                logger.warning("input device lost (%s), retrying in 2s", exc)
                await asyncio.sleep(2)

    async def _run_dummy(self) -> None:
        """Fallback used on dev machines / CI without a real keypad node."""
        loop = asyncio.get_event_loop()
        while True:
            await asyncio.sleep(0.15)
            self._record(loop.time())


def calculate_unstable_rate(timestamps: deque[float]) -> float:
    """Rhythm-stability UR from raw click intervals (stddev of intervals * 10).

    Note: this is self-referential rhythm UR — it needs no beatmap and works
    outside gameplay. True osu! UR (stddev of hit errors vs note times) comes
    from telemetry's hitErrorArray and takes precedence in the overlay.
    """
    if len(timestamps) < 8:
        return 0.0
    ts = list(timestamps)[-64:]
    intervals = [b - a for a, b in zip(ts, ts[1:])]
    # reject pauses (breaks, menu time): keep intervals under 400 ms
    intervals = [i for i in intervals if i < 0.4]
    if len(intervals) < 4:
        return 0.0
    mean = sum(intervals) / len(intervals)
    variance = sum((x - mean) ** 2 for x in intervals) / len(intervals)
    return (variance ** 0.5) * 1000 * 10
