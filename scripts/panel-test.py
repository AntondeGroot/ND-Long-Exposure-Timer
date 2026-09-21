#!/usr/bin/env python3
"""Push solid frames at the panel, to tell a data fault from a software one.

RUNS ON THE PI, with nd-timer stopped:

    sudo systemctl stop nd-timer
    ./.venv/bin/python scripts/panel-test.py

A frame of all-black is one byte repeated: there is no layout, no font, no
arithmetic and nothing of ours in it. If that comes out as anything other than
a uniform block, the bytes are not arriving intact - which is the ribbon or the
connector, not the code. If the solids are clean and only our screens are noise,
the fault is ours.
"""

from __future__ import annotations

import sys
import time

PANEL_MODULE = "waveshare_epd.epd2in13_V4"

# 122 x 250, one bit per pixel, eight to a byte along each row.
WIDTH, HEIGHT = 122, 250
FRAME_BYTES = (WIDTH // 8 + (1 if WIDTH % 8 else 0)) * HEIGHT

BLACK, WHITE = 0x00, 0xFF


def main() -> int:
    try:
        module = __import__(PANEL_MODULE, fromlist=["EPD"])
    except ImportError as exc:
        print(f"panel driver {PANEL_MODULE} unavailable: {exc}", file=sys.stderr)
        return 1

    panel = module.EPD()
    panel.init()
    print(f"panel says it is {panel.width} x {panel.height}; a frame is {FRAME_BYTES} bytes")
    if (panel.width, panel.height) != (WIDTH, HEIGHT):
        print("  ^ that does not match 122x250 - wrong driver for this panel?")

    for name, fill in (("all black", BLACK), ("all white", WHITE), ("all black again", BLACK)):
        print(f"  {name} ...", flush=True)
        panel.display([fill] * FRAME_BYTES)
        time.sleep(2)

    print("sleeping the panel")
    panel.sleep()
    print()
    print("Uniform blocks  -> the data path is fine, look at our frames.")
    print("Noise or bands  -> the bytes are not arriving: reseat the ribbon.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
