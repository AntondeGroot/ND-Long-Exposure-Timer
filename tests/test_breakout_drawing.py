"""The committed soldering guide must still be what the layout draws.

The layout in scripts/breakout_drawing/layout.py is the one source of truth; the SVGs
in docs/breakout/ are its output. An SVG edited by hand, or a layout changed without
rerunning the script, shows up here rather than as a board soldered from a stale picture.
"""

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_SCRIPT = REPO / "scripts" / "draw-breakout.py"
_spec = importlib.util.spec_from_file_location("draw_breakout", _SCRIPT)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

PAGES = _module.pages()


@pytest.mark.parametrize("name", sorted(PAGES))
def test_guide_image_matches_the_layout(name):
    committed = _module.OUTPUT_DIR / name
    assert committed.exists(), f"no {name} - run scripts/draw-breakout.py"
    # A bool rather than `==` on the strings, so a failure names the file instead of
    # dumping two thousand lines of SVG.
    matches = committed.read_text() == PAGES[name]
    assert matches, f"{name} differs from what the layout draws - rerun scripts/draw-breakout.py and commit it"
