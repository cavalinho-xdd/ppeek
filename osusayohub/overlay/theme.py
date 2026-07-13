"""Overlay color themes, selected by the active osu! skin name.

tosu reports the lazer skin via ``settings.skin.name`` (read from
``SkinManager.CurrentSkin`` in game memory). Skin names are long and
locale-heavy (e.g. "{S} FOOL MOON NIGHT/칵스(...) (Spoo)"), so themes
are matched by case-insensitive substring rather than exact equality —
robust against version suffixes and lazer import renames.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtGui import QColor

FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"


def ensure_theme_fonts() -> None:
    """Register bundled Readex Pro with Qt when the system lacks it."""
    from PyQt6.QtGui import QFontDatabase

    if "Readex Pro" in QFontDatabase.families():
        return
    for fname in ("ReadexPro-Regular.ttf", "ReadexPro-bold.ttf"):
        path = FONTS_DIR / fname
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))


@dataclass(frozen=True)
class OverlayTheme:
    name: str
    scene: str            # "night" (ink sky) or "pastel" (Blue Archive motifs)
    ink: QColor           # primary line/text color
    body_fill: QColor     # solid fill behind hatched/decorated shapes
    miss: QColor          # miss counter accent
    bg_top: QColor
    bg_bottom: QColor
    accent: QColor        # secondary hue for scene decoration
    deco_red: QColor      # tertiary pop color (Arona's red halo string)
    font: str = "Sans"


FULL_MOON_NIGHT = OverlayTheme(
    name="full-moon-night",
    scene="night",
    ink=QColor(240, 240, 245),
    body_fill=QColor(8, 8, 12, 235),
    miss=QColor(235, 110, 110),
    bg_top=QColor(10, 10, 16, 215),
    bg_bottom=QColor(4, 4, 8, 235),
    accent=QColor(240, 240, 245),
    deco_red=QColor(235, 110, 110),
)

# Arona & Plana (Blue Archive), by Kitazaki Hinata. Colors taken from the
# skin's own skin.ini: Combo1 147,216,255 / MenuGlow 88,178,235 /
# SliderBorder 44,56,67 / mania note 14,23,30; text ink #ceecf9 is the UI
# hue shown in the skin's pause-screen art. The skin ships only bitmap
# digit fonts, so the closest installed rounded sans (Readex Pro) stands
# in for its rounded lettering; Qt falls back to Sans when absent.
ARONA_PLANA = OverlayTheme(
    name="arona-plana",
    scene="pastel",
    ink=QColor(206, 236, 249),
    body_fill=QColor(14, 23, 30, 235),
    miss=QColor(228, 90, 105),
    bg_top=QColor(16, 30, 44, 215),
    bg_bottom=QColor(8, 16, 26, 235),
    accent=QColor(88, 178, 235),
    deco_red=QColor(228, 90, 105),
    font="Readex Pro",
)

DEFAULT_THEME = FULL_MOON_NIGHT

# first substring hit wins; needles are matched casefolded
SKIN_THEMES: list[tuple[str, OverlayTheme]] = [
    ("fool moon night", FULL_MOON_NIGHT),
    ("hk7205", ARONA_PLANA),
    ("アロナ", ARONA_PLANA),
]


def resolve_theme(skin_name: str) -> OverlayTheme:
    lowered = skin_name.casefold()
    for needle, theme in SKIN_THEMES:
        if needle.casefold() in lowered:
            return theme
    return DEFAULT_THEME
