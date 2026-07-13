"""osu!lazer local WebSocket telemetry listener."""
from __future__ import annotations

import asyncio
import enum
import json
import logging
from dataclasses import dataclass, field
from typing import Callable

import websockets

logger = logging.getLogger(__name__)

# tosu v2 API — matches TelemetryFrame.from_json field paths
DEFAULT_URI = "ws://127.0.0.1:24050/websocket/v2"


class GameState(enum.Enum):
    """Coarse osu! client state, derived from tosu/gosumemory `state` numbers."""

    MENU = 0
    EDIT = 1
    PLAY = 2
    EXIT = 3
    SELECT_EDIT = 4
    SELECT_PLAY = 5
    SELECT_DRAWINGS = 6
    RESULT_SCREEN = 7
    UPDATE = 8
    BUSY = 9
    UNKNOWN = 10
    LOBBY = 11
    MATCH_SETUP = 12
    SELECT_MULTI = 13
    RANKING_VS = 14
    ONLINE_SELECTION = 15
    OPTIONS_OFFSET_WIZARD = 16
    RANKING_TAG_COOP = 17
    RANKING_TEAM = 18
    BEATMAP_IMPORT = 19
    PACKAGE_UPDATER = 20
    BENCHMARK = 21
    TOURNEY = 22
    CHARTS = 23

    @classmethod
    def from_raw(cls, value: object) -> "GameState":
        try:
            return cls(int(value))  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return cls.UNKNOWN


@dataclass(slots=True)
class TelemetryFrame:
    state: GameState = GameState.UNKNOWN
    connected: bool = False

    # live play values
    pp: float = 0.0
    pp_if_fc: float = 0.0
    combo: int = 0
    max_combo: int = 0
    accuracy: float = 0.0
    grade: str = ""
    hp: float = 0.0

    hits_300: int = 0
    hits_100: int = 0
    hits_50: int = 0
    hits_miss: int = 0

    # hit errors in ms relative to note time (signed); source for true UR
    hit_errors: list[float] = field(default_factory=list)
    unstable_rate: float = 0.0

    # beatmap metadata
    artist: str = ""
    title: str = ""
    difficulty: str = ""
    stars: float = 0.0
    bpm: float = 0.0

    # active skin name (lazer: read from SkinManager by tosu; empty if unavailable)
    skin: str = ""

    @property
    def in_gameplay(self) -> bool:
        return self.state == GameState.PLAY

    @classmethod
    def from_json(cls, payload: dict) -> "TelemetryFrame":
        """Parse a tosu/gosumemory v2-style payload; tolerate missing keys."""
        play = payload.get("play", payload.get("gameplay", {})) or {}
        pp_block = play.get("pp", {}) or {}
        combo_block = play.get("combo", {}) or {}
        hits = play.get("hits", {}) or {}
        beatmap = payload.get("beatmap", {}) or {}
        meta = beatmap.get("metadata", beatmap) or {}
        stats = beatmap.get("stats", {}) or {}

        raw_state = payload.get("state", {})
        if isinstance(raw_state, dict):
            raw_state = raw_state.get("number", 10)

        hit_errors = play.get("hitErrorArray", hits.get("hitErrorArray", [])) or []

        settings = payload.get("settings", {}) or {}
        skin_block = settings.get("skin", {}) or {}

        return cls(
            state=GameState.from_raw(raw_state),
            connected=True,
            pp=_num(pp_block.get("current")),
            pp_if_fc=_num(pp_block.get("fc")),
            combo=int(_num(combo_block.get("current"))),
            max_combo=int(_num(combo_block.get("max"))),
            accuracy=_num(play.get("accuracy")),
            grade=str((play.get("rank", {}) or {}).get("current", play.get("grade", ""))),
            hp=_num((play.get("healthBar", {}) or {}).get("normal", play.get("hp"))),
            hits_300=int(_num(hits.get("300"))),
            hits_100=int(_num(hits.get("100"))),
            hits_50=int(_num(hits.get("50"))),
            hits_miss=int(_num(hits.get("0"))),
            hit_errors=[float(x) for x in hit_errors if isinstance(x, (int, float))],
            unstable_rate=_num(hits.get("unstableRate", play.get("unstableRate"))),
            artist=str(meta.get("artist", "")),
            title=str(meta.get("title", "")),
            difficulty=str(meta.get("difficulty", meta.get("version", ""))),
            stars=_num((stats.get("stars", {}) or {}).get("total", stats.get("SR"))),
            bpm=_num((stats.get("bpm", {}) or {}).get("common", stats.get("BPM"))),
            skin=str(skin_block.get("name", "")),
        )


def _num(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


class TelemetryListener:
    """Reconnecting WebSocket client that yields TelemetryFrame updates."""

    def __init__(
        self,
        uri: str = DEFAULT_URI,
        on_frame: Callable[[TelemetryFrame], None] | None = None,
        on_disconnect: Callable[[], None] | None = None,
    ):
        self._uri = uri
        self.on_frame = on_frame
        self.on_disconnect = on_disconnect
        self._task: asyncio.Task | None = None
        self._stop = False

    def start(self) -> None:
        self._stop = False
        self._task = asyncio.ensure_future(self._run())

    def stop(self) -> None:
        self._stop = True
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        while not self._stop:
            try:
                async with websockets.connect(self._uri, max_size=2**22) as ws:
                    logger.info("connected to %s", self._uri)
                    async for message in ws:
                        try:
                            frame = TelemetryFrame.from_json(json.loads(message))
                        except (json.JSONDecodeError, TypeError) as exc:
                            logger.debug("bad telemetry payload: %s", exc)
                            continue
                        if self.on_frame:
                            self.on_frame(frame)
            except (OSError, websockets.exceptions.WebSocketException) as exc:
                logger.debug("telemetry connection lost: %s, retrying in 2s", exc)
                if self.on_disconnect:
                    self.on_disconnect()
                await asyncio.sleep(2)
