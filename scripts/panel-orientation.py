#!/usr/bin/env python3
"""Tell a data fault from an orientation fault, in one run.

RUNS ON THE PI, with nd-timer stopped:

    sudo systemctl stop nd-timer
    ./.venv/bin/python scripts/panel-orientation.py

Solid frames come first: a frame of one repeated byte has no layout, no font
and no arithmetic in it, so anything other than a uniform block means the bytes
are not arriving - the ribbon or the connector, not the code.

Then a letter F, which is the point of the exercise. F is asymmetric in both
axes, so where its arms end up says exactly what is happening: arms to the
right and at the top is correct, arms to the left is a horizontal mirror, arms
at the bottom is a vertical flip. A solid frame cannot tell you any of that.
"""

from __future__ import annotations

import sys
import time

from PIL import Image, ImageDraw

PANEL_MODULE = "waveshare_epd.epd2in13_V4"
WIDTH, HEIGHT = 122, 250
FRAME_BYTES = (WIDTH // 8 + (1 if WIDTH % 8 else 0)) * HEIGHT

BLACK, WHITE = 0x00, 0xFF


def letter_f() -> list[int]:
    """A big F in the top-left, drawn the same way the screens are drawn."""
    frame = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(frame)
    draw.rectangle((12, 12, 34, 170), fill=0)   # stem, down the left
    draw.rectangle((12, 12, 105, 34), fill=0)   # top arm, the long one
    draw.rectangle((12, 78, 80, 100), fill=0)   # middle arm, shorter
    return list(frame.tobytes())


def main() -> int:
    try:
        module = __import__(PANEL_MODULE, fromlist=["EPD"])
    except ImportError as exc:
        print(f"panel driver {PANEL_MODULE} unavailable: {exc}", file=sys.stderr)
        return 1

    panel = module.EPD()
    panel.init()
    print(f"panel says it is {panel.width} x {panel.height}; a frame is {FRAME_BYTES} bytes")

    for name, byte in (("all black", BLACK), ("all white", WHITE)):
        print(f"  {name} - expect a uniform block, edge to edge")
        panel.display([byte] * FRAME_BYTES)
        time.sleep(2)

    print("  letter F - note which side the arms point and whether it sits at the top")
    panel.display(letter_f())

    panel.sleep()
    print("done. The F stays on the panel; the service is still stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
