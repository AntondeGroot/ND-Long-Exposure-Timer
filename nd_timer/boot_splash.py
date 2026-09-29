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

# Word for the application that the panel has had one clean, complete refresh
# this boot, so it need not start from white. On /run, a tmpfs, so it cannot
# outlive the boot it describes: after a power cut it is simply not there.
DRAWN_MARKER = Path("/run/nd-timer-splash-drawn")

# Word that the splash has let go of the panel, drawn or not. The application no
# longer starts after this unit - it spends the splash's refresh importing, which
# is most of what it costs to start - so it waits for this instead, just before
# it opens the panel. Two processes on the panel at once is what filled the
# screen with noise on 2026-09-24.
DONE_MARKER = Path("/run/nd-timer-splash-done")

# How the application tells that a splash is coming at all: the unit is
# installed, and the buffer its ConditionPathExists wants is there. Without both
# it would wait out SPLASH_DONE_WAIT_SECONDS for a splash that never runs.
SPLASH_UNIT = Path("/etc/systemd/system/nd-timer-splash.service")

# Longer than a splash takes (4.5s drawn, 20s at most waiting for SPI), and short
# enough that a splash killed before it could say so costs half a minute, once.
SPLASH_DONE_WAIT_SECONDS = 30.0
SPLASH_DONE_POLL_SECONDS = 0.05


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


def leave_word() -> None:
    """Tell the application the panel is in a known state.

    Only ever a saving: without the marker the application clears the panel as
    it always has, so failing to write it costs time and is not worth failing
    a splash that has already drawn.
    """
    try:
        DRAWN_MARKER.touch()
    except OSError as exc:
        print(f"could not leave word for the application: {exc}", file=sys.stderr)


def wait_for_spi() -> bool:
    """True once the SPI node is there, False if it never turned up."""
    deadline = time.monotonic() + SPI_WAIT_SECONDS
    while not SPI_DEVICE.exists():
        if time.monotonic() > deadline:
            return False
        time.sleep(SPI_POLL_SECONDS)
    return True


def wait_for_splash() -> bool:
    """Block until the splash has let go of the panel. False if it never said so.

    Returns at once when no splash is going to run.
    """
    if not (SPLASH_UNIT.exists() and SPLASH_BUFFER.exists()):
        return True
    deadline = time.monotonic() + SPLASH_DONE_WAIT_SECONDS
    while not DONE_MARKER.exists():
        if time.monotonic() > deadline:
            return False
        time.sleep(SPLASH_DONE_POLL_SECONDS)
    return True


def main() -> int:
    """Draw the splash, and say it is done however that went."""
    try:
        return draw()
    finally:
        mark_done()


def mark_done() -> None:
    """Tell the application the panel is free. Never raises: see leave_word()."""
    try:
        DONE_MARKER.touch()
    except OSError as exc:
        print(f"could not say the splash is done: {exc}", file=sys.stderr)


def draw() -> int:
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

    leave_word()
    print(f"splash on the panel in {time.monotonic() - started:.2f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
