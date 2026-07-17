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

# -- color-palette themes -------------------------------------------------
# Not tied to any osu! skin: all six reuse the universal "night" scene and
# differ only in palette, so they stay deliberately close in feel. Colors
# come from each scheme's canonical spec; ink carries the scheme's
# signature hue (the night scene tints everything with ink, so a neutral
# foreground would make all six look alike). Nord/Tokyo Night keep their
# characteristic cool foregrounds. Quicksand for the whole set.

GRUVBOX = OverlayTheme(
    name="gruvbox",
    scene="night",
    ink=QColor(251, 90, 68),            # bright red, lifted for contrast
    body_fill=QColor(29, 32, 33, 235),  # bg0_h #1d2021
    miss=QColor(251, 73, 52),           # bright red #fb4934
    bg_top=QColor(40, 40, 40, 215),     # bg0 #282828
    bg_bottom=QColor(29, 32, 33, 235),
    accent=QColor(251, 73, 52),
    deco_red=QColor(254, 128, 25),      # bright orange #fe8019
    font="Quicksand",
)

EVERFOREST = OverlayTheme(
    name="everforest",
    scene="night",
    ink=QColor(167, 192, 128),          # green #a7c080
    body_fill=QColor(35, 42, 46, 235),  # bg0 #232a2e
    miss=QColor(230, 126, 128),         # red #e67e80
    bg_top=QColor(45, 53, 59, 215),     # bg1 #2d353b
    bg_bottom=QColor(35, 42, 46, 235),
    accent=QColor(167, 192, 128),       # green #a7c080
    deco_red=QColor(230, 126, 128),
    font="Quicksand",
)

NORD = OverlayTheme(
    name="nord",
    scene="night",
    ink=QColor(216, 222, 233),          # snow storm #d8dee9
    body_fill=QColor(36, 41, 51, 235),  # deep polar night
    miss=QColor(191, 97, 106),          # aurora red #bf616a
    bg_top=QColor(46, 52, 64, 215),     # polar night #2e3440
    bg_bottom=QColor(36, 41, 51, 235),
    accent=QColor(129, 161, 193),       # frost blue #81a1c1
    deco_red=QColor(136, 192, 208),     # frost cyan #88c0d0
    font="Quicksand",
)

TOKYO_NIGHT = OverlayTheme(
    name="tokyo-night",
    scene="night",
    ink=QColor(192, 202, 245),          # fg #c0caf5
    body_fill=QColor(22, 22, 30, 235),  # bg dark #16161e
    miss=QColor(247, 118, 142),         # red #f7768e
    bg_top=QColor(26, 27, 38, 215),     # bg #1a1b26
    bg_bottom=QColor(22, 22, 30, 235),
    accent=QColor(125, 207, 255),       # cyan #7dcfff
    deco_red=QColor(187, 154, 247),     # purple #bb9af7
    font="Quicksand",
)

CATPPUCCIN = OverlayTheme(
    name="catppuccin",
    scene="night",
    ink=QColor(203, 166, 247),          # mauve #cba6f7
    body_fill=QColor(24, 24, 37, 235),  # mantle #181825
    miss=QColor(243, 139, 168),         # red #f38ba8
    bg_top=QColor(30, 30, 46, 215),     # base #1e1e2e
    bg_bottom=QColor(17, 17, 27, 235),  # crust #11111b
    accent=QColor(203, 166, 247),       # mauve #cba6f7
    deco_red=QColor(245, 194, 231),     # pink #f5c2e7
    font="Quicksand",
)

AYU = OverlayTheme(
    name="ayu",
    scene="night",
    ink=QColor(230, 180, 80),           # yellow #e6b450
    body_fill=QColor(13, 16, 23, 235),  # #0d1017
    miss=QColor(240, 113, 120),         # red #f07178
    bg_top=QColor(16, 20, 30, 215),
    bg_bottom=QColor(10, 14, 20, 235),  # bg #0a0e14
    accent=QColor(230, 180, 80),        # yellow #e6b450
    deco_red=QColor(255, 143, 64),      # orange #ff8f40
    font="Quicksand",
)

PALETTE_THEMES: list[OverlayTheme] = [
    GRUVBOX, EVERFOREST, NORD, TOKYO_NIGHT, CATPPUCCIN, AYU,
]

# first substring hit wins; needles are matched casefolded
SKIN_THEMES: list[tuple[str, OverlayTheme]] = [
    ("freedom dive", FREEDOM_DIVE),
    ("fool moon night", FULL_MOON_NIGHT),
    ("hk7205", ARONA_PLANA),
    ("アロナ", ARONA_PLANA),
    ("clearblack", CLEAR_BLACK),
    ("clear black", CLEAR_BLACK),
]

# every theme addressable by its stable name — used by the manual override
# (settings key overlay/theme_override) and the config-hub Apply buttons
THEMES_BY_NAME: dict[str, OverlayTheme] = {
    t.name: t
    for t in (FULL_MOON_NIGHT, ARONA_PLANA, FREEDOM_DIVE, CLEAR_BLACK, *PALETTE_THEMES)
}


def resolve_theme(skin_name: str) -> OverlayTheme:
    lowered = skin_name.casefold()
    for needle, theme in SKIN_THEMES:
        if needle.casefold() in lowered:
            return theme
    return DEFAULT_THEME
