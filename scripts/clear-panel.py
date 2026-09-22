#!/usr/bin/env python3
"""Wipe the e-paper panel back to white.

RUNS ON THE PI, with nd-timer stopped - the service holds the SPI bus:

    sudo systemctl stop nd-timer
    ./.venv/bin/python scripts/clear-panel.py
    sudo systemctl start nd-timer

Losing power partway through a refresh leaves the panel holding whatever state
its particles were left in, which reads as noise. Nothing is damaged and a full
refresh fixes it - but an ordinary draw sometimes will not, because the driver
is writing differences against a previous image the panel no longer holds.

It finishes by sleeping the panel rather than leaving it powered, which is how
e-paper is meant to be left: the image stays without current behind it.
"""

from __future__ import annotations

import sys

PANEL_MODULE = "waveshare_epd.epd2in13_V4"


def main() -> int:
    try:
        module = __import__(PANEL_MODULE, fromlist=["EPD"])
    except ImportError as exc:
        print(f"panel driver {PANEL_MODULE} unavailable: {exc}", file=sys.stderr)
        return 1

    panel = module.EPD()
    print("initialising")
    panel.init()

    # A full buffer of white through display(), not the driver's Clear(): after
    # an interrupted refresh Clear leaves the noise where it is, which is what
    # it did the one time it mattered. Twice, because one pass leaves a ghost.
    white = [0xFF] * (122 // 8 + 1) * 250
    for pass_number in (1, 2):
        print(f"clearing, pass {pass_number}")
        panel.display(white)

    print("sleeping the panel")
    panel.sleep()
    print("done - white. Start the service again and it will draw.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
