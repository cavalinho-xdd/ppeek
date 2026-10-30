"""Render README screenshots of the overlay without running the full app.

Thin wrapper around ppeek.overlay.preview: renders each skin tribute's
HUD offscreen at 2x and writes transparent PNGs to docs/screenshots/.

Usage:
    python scripts/render_screenshots.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtGui import QGuiApplication

from ppeek.confighub.skins import SKIN_CATALOG
from ppeek.overlay.preview import render_theme_preview
from ppeek.overlay.theme import resolve_theme

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"


def main() -> None:
    app = QGuiApplication(sys.argv)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for entry in SKIN_CATALOG:
        img = render_theme_preview(entry.skin_name)
        out = OUT_DIR / (resolve_theme(entry.skin_name).name + ".png")
        img.save(str(out))
        print("wrote", out)
    app.quit()


if __name__ == "__main__":
    main()
