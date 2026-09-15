"""Put the splash on the panel as early in boot as possible.

A Pi Zero takes the better part of a minute to reach the application, and a blank
panel for that long reads as a device that has not switched on. This runs as soon
as SPI exists and pushes a buffer packed at build time - so it imports the panel
driver and nothing else. Pillow alone costs several seconds here, which would
defeat the purpose.

E-paper holds its image without power, so the splash also survives the gap
between switching on and this running.
"""

from __future__ import annotations

import sys
from pathlib import Path

SPLASH_BUFFER = Path(__file__).resolve().parent.parent / "assets" / "splash.bin"

# Which panel revision is fitted; the driver module name is the only difference.
PANEL_MODULE = "waveshare_epd.epd2in13_V4"


def main() -> int:
    if not SPLASH_BUFFER.exists():
        print(f"no packed splash at {SPLASH_BUFFER} - run scripts/render-screens.py", file=sys.stderr)
        return 1

    try:
        module = __import__(PANEL_MODULE, fromlist=["EPD"])
    except ImportError as exc:
        print(f"panel driver {PANEL_MODULE} unavailable: {exc}", file=sys.stderr)
        return 1

    panel = module.EPD()
    panel.init()
    panel.display(list(SPLASH_BUFFER.read_bytes()))

    # Sleep rather than leaving it powered: the image stays, the panel does not
    # need to be held awake to show it, and the application will init its own.
    panel.sleep()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
