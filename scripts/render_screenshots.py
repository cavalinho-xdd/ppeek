"""Render README screenshots of the overlay without running the full app.

Thin wrapper around osusayohub.overlay.preview: renders each theme's
showcase preview offscreen and writes 2x-scaled transparent PNGs to
docs/screenshots/.

Usage:
    QT_QPA_PLATFORM=offscreen python scripts/render_screenshots.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication

from osusayohub.confighub.skins import SKIN_CATALOG
from osusayohub.overlay.preview import render_theme_preview
from osusayohub.overlay.theme import resolve_theme

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"


def main() -> None:
    app = QApplication(sys.argv)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for entry in SKIN_CATALOG:
        img = render_theme_preview(entry.skin_name, entry.anim_t)
        out = OUT_DIR / (resolve_theme(entry.skin_name).name + ".png")
        img.save(str(out))
        print("wrote", out)
    app.quit()


if __name__ == "__main__":
    main()
