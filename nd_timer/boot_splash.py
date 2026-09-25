"""Put the splash on the panel as early in boot as possible.

A Pi Zero takes the better part of a minute to reach the application, and a blank
panel for that long reads as a device that has not switched on. This runs as soon
as SPI exists and pushes a buffer packed at build time - so it imports the panel
transport and nothing else. Pillow alone costs several seconds here, which would
defeat the purpose, and the vendor driver costs nine (see nd_timer/fast_panel.py).

E-paper holds its image without power, so the splash also survives the gap
between switching on and this running.

The unit that runs this opts out of systemd's default ordering to start early,
which means /dev/spidev0.0 may not exist yet - so the wait for it is here rather
than a ConditionPathExists that would silently skip the splash.
"""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

SPLASH_BUFFER = Path(__file__).resolve().parent.parent / "assets" / "splash.bin"

# The node udev makes once the SPI driver has bound, and how long it is given.
SPI_DEVICE = Path("/dev/spidev0.0")
SPI_WAIT_SECONDS = 20.0
SPI_POLL_SECONDS = 0.05


@contextmanager
def timed(stage: str):
    """Report what one stage cost, to stderr.

    This unit was the largest single thing in the boot - 18.5s of ~58s - and
    nothing said which part of it was slow. The unit sets StandardError=journal,
    so a boot answers that on its own.
    """
    started = time.monotonic()
    try:
        yield
    finally:
        print(f"    {stage}: {time.monotonic() - started:.2f}s", file=sys.stderr)


def open_panel():
    """The panel, driven straight from spidev and lgpio.

    Imported here rather than at module scope so that a missing dependency is a
    reported failure instead of a traceback before main() has said anything.
    """
    from nd_timer.fast_panel import Panel

    return Panel.open()


def wait_for_spi() -> bool:
    """True once the SPI node is there, False if it never turned up."""
    deadline = time.monotonic() + SPI_WAIT_SECONDS
    while not SPI_DEVICE.exists():
        if time.monotonic() > deadline:
            return False
        time.sleep(SPI_POLL_SECONDS)
    return True


def main() -> int:
    started = time.monotonic()

    if not SPLASH_BUFFER.exists():
        print(f"no packed splash at {SPLASH_BUFFER} - run scripts/render-screens.py", file=sys.stderr)
        return 1

    with timed("wait for spi"):
        if not wait_for_spi():
            print(f"{SPI_DEVICE} never appeared - is dtparam=spi=on set?", file=sys.stderr)
            return 1

    with timed("open panel"):
        try:
            panel = open_panel()
        except ImportError as exc:
            print(f"panel transport unavailable: {exc}", file=sys.stderr)
            return 1

    # Anything that goes wrong from here has to let the pins go. Holding RESET
    # low while the application initialises the panel behind us is what put
    # noise on the screen the first time this failed part-way through.
    try:
        with timed("init"):
            panel.init()
        with timed("display"):
            panel.display(SPLASH_BUFFER.read_bytes())

        # Sleep rather than leaving it powered: the image stays, the panel does
        # not need to be held awake to show it, and it hands the pins back to
        # the application, which wants the same four.
        with timed("sleep"):
            panel.sleep()
    except Exception as exc:
        panel.abandon()
        print(f"the panel was not drawn: {exc!r}", file=sys.stderr)
        return 1

    print(f"splash on the panel in {time.monotonic() - started:.2f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
