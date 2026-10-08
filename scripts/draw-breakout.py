#!/usr/bin/env python3
"""Draw the Breakout Pi Zero soldering guide to docs/breakout/.

One overview of the finished board, one image per step, and the three cables. All of them come from
scripts/breakout_drawing/layout.py, so a change to the layout is a change to that file
followed by a rerun of this one - never an edit to an SVG.

These images are committed, and the test suite checks they still match the layout.

Run after any change to the layout:  ./scripts/draw-breakout.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.breakout_drawing.cable_page import cable_page  # noqa: E402
from scripts.breakout_drawing.cables import DATA_CABLE, POWER_CABLE  # noqa: E402
from scripts.breakout_drawing.compose import overview, step_page  # noqa: E402
from scripts.breakout_drawing.jst_cable import jst_cable_page  # noqa: E402
from scripts.breakout_drawing.layout import STEPS  # noqa: E402

OUTPUT_DIR = REPO / "docs" / "breakout"


def pages() -> dict[str, str]:
    """Every image, by file name."""
    steps = {f"step-{number}.svg": step_page(number) for number in range(1, len(STEPS) + 1)}
    return {
        "overview.svg": overview(),
        **steps,
        "jst-cable.svg": jst_cable_page(),
        "power-cable.svg": cable_page(POWER_CABLE),
        "data-cable.svg": cable_page(DATA_CABLE),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, svg in pages().items():
        (OUTPUT_DIR / name).write_text(svg)
        print(f"wrote {OUTPUT_DIR / name}")


if __name__ == "__main__":
    main()
