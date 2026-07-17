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
    """Register all bundled fonts with Qt."""
    from PyQt6.QtGui import QFontDatabase

    if not FONTS_DIR.exists():
        return
    
    for path in FONTS_DIR.iterdir():
        if path.suffix.lower() in (".ttf", ".otf"):
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
    font="Gaegu",
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
    font="Quicksand",
)

DEFAULT_THEME = FULL_MOON_NIGHT

FREEDOM_DIVE = OverlayTheme(
    name="freedom-dive",
    scene="freedom",
    ink=QColor(255, 255, 255),
    body_fill=QColor(12, 18, 48, 235),
    miss=QColor(255, 120, 140),        # pink-red like the skin's ✕ miss marker
    bg_top=QColor(25, 40, 85, 215),    # cosmic blue from the menu-background
    bg_bottom=QColor(8, 12, 35, 240),  # deep space void
    accent=QColor(150, 230, 255),      # Combo1 light cyan
    deco_red=QColor(255, 125, 177),    # Combo2 pink
    font="Fredoka",
)

# clearBlack by FakeCarpetGrass: pure black playfield, no bitmap decoration at
# all — the entire skin is one crosshair-only hitcircle whose ring is a
# full-spectrum rainbow gradient (see skin.ini Combo1..5: 164,100,240 /
# 230,110,150 / 240,150,255 / 100,200,200 / 130,120,255), a matching
# rainbow approach circle, and a soft blue-violet cursor glow. Nothing
# else is skinned — hit-bursts, sliders, spinner all fall back to
# osu!'s stock look, so this theme leans on that same rainbow-ring +
# crosshair motif rather than borrowed skin art.
CLEAR_BLACK = OverlayTheme(
    name="clear-black",
    scene="clearblack",
    ink=QColor(245, 245, 248),
    body_fill=QColor(4, 4, 5, 235),
    miss=QColor(230, 110, 150),        # Combo2 rose
    bg_top=QColor(10, 10, 11, 215),
    bg_bottom=QColor(2, 2, 2, 245),
    accent=QColor(140, 150, 255),      # cursor glow blue-violet
    deco_red=QColor(230, 110, 150),    # Combo2 rose
)

# first substring hit wins; needles are matched casefolded
SKIN_THEMES: list[tuple[str, OverlayTheme]] = [
    ("freedom dive", FREEDOM_DIVE),
    ("fool moon night", FULL_MOON_NIGHT),
    ("hk7205", ARONA_PLANA),
    ("アロナ", ARONA_PLANA),
    ("clearblack", CLEAR_BLACK),
    ("clear black", CLEAR_BLACK),
]


def resolve_theme(skin_name: str) -> OverlayTheme:
    lowered = skin_name.casefold()
    for needle, theme in SKIN_THEMES:
        if needle.casefold() in lowered:
            return theme
    return DEFAULT_THEME
