#!/usr/bin/env python3
"""The device itself: buttons in, frames out, gphoto2 in between.

RUNS ON THE PI. Everything it drives has been testable without hardware all
along - nd_timer.device is the state machine the browser simulator drives, and
nd_timer.ui draws the frames - so this file is only the three things that need
real hardware: the buttons, the panel, and the camera.

systemd starts it from the repo root (see scripts/setup-pi.sh). It has to live
here rather than in nd_timer/__main__.py: the unit runs the entry point by path,
which puts that file's own directory on sys.path, and `import nd_timer` then
fails for a file inside the package.
"""

from __future__ import annotations

import queue
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nd_timer.camera import Camera, CameraError, nearest_timed_shutter  # noqa: E402
from nd_timer.device import Device  # noqa: E402
from nd_timer.exposure import needs_bulb  # noqa: E402
from nd_timer.ui.panel import to_panel_bytes  # noqa: E402
from nd_timer.ui.screens import (  # noqa: E402
    CountdownScreen,
    DelayScreen,
    MainScreen,
    SplashScreen,
    render_countdown,
    render_delay,
    render_main,
    render_splash,
)
from nd_timer.ui.settings import SettingsScreen, render_settings  # noqa: E402

# ---------------------------------------------------------------------- PINS
#
# BCM numbering, switches to ground, internal pull-ups. CORRECT THESE to match
# how the five-way and the two buttons are actually wired.
#
# These defaults avoid the pins the e-paper HAT already owns - 8, 9, 10, 11 for
# SPI and 17, 24, 25 for reset, busy and data/command - so they are a safe place
# to start, not a description of your board.

PINS = {
    "up": 6,
    "down": 19,
    "left": 5,
    "right": 26,
    "centre": 13,
    "sync": 20,
    "shoot": 21,
}

# ---------------------------------------------------------------------------

PANEL_MODULE = "waveshare_epd.epd2in13_V4"

# Long enough not to fire on a firm press, short enough to feel like a decision.
# It is what the countdown's "HOLD TO CANCEL" has been promising all along.
HOLD_SECONDS = 1.2

# The five-way is read on press for the feedback; SHOOT is read on release,
# because until it comes up we do not know which of its two meanings it had.
DEBOUNCE_SECONDS = 0.05

# How often the loop wakes. The panel takes about a second to draw, so this is
# about how soon a press is noticed, not how often anything is redrawn.
TICK_SECONDS = 0.05

# How often the screen is worked out when nothing has been pressed. Building one
# runs the solver, which on an ARMv6 is the most expensive thing here by far -
# and the answer only moves on a press or on a ten-second step, so asking twenty
# times a second is twenty times the work for the same picture.
REDRAW_INTERVAL_SECONDS = 1.0

RENDERERS = {
    SplashScreen: render_splash,
    MainScreen: render_main,
    DelayScreen: render_delay,
    CountdownScreen: render_countdown,
    SettingsScreen: render_settings,
}


def _battery_percent() -> int:
    """What the UPS HAT has left.

    TODO: needs the HAT's model. They are mostly an I2C fuel gauge, but the
    address and the register layout differ per board, so there is nothing
    honest to write here until that is known. The status bar draws whatever
    this returns.
    """
    return 100


class Panel:
    """The e-paper panel, drawn only when the screen has actually changed.

    The comparison is on the screen rather than on the pixels, because drawing
    the frame is the expensive half: PIL laying out text on an ARMv6 is tens of
    milliseconds, and the loop asks twenty times a second. Comparing first means
    a screen that has not changed costs a dataclass comparison instead.

    Every refresh also costs about a second of the panel's time and a little of
    its life, which is why the screens above are built to hold still.
    """

    def __init__(self) -> None:
        module = __import__(PANEL_MODULE, fromlist=["EPD"])
        self._panel = module.EPD()
        self._panel.init()
        self._showing = None

    def show(self, screen) -> None:
        if screen == self._showing:
            return
        frame = RENDERERS[type(screen)](screen)
        self._panel.display(list(to_panel_bytes(frame)))
        self._showing = screen

    def rest(self) -> None:
        """Sleep the panel, which keeps the image without holding it awake."""
        self._panel.sleep()


class Buttons:
    """The seven switches, read straight from the chip.

    gpiozero was the obvious choice and cost fifteen percent of a core doing
    nothing at all - its lgpio backend runs a busy loop whatever you ask of it,
    the same cost for one button as for six. On something that runs off a
    battery that is a poor trade for an interrupt nobody needs: a finger is not
    fast, and the loop already wakes twenty times a second.

    So the pins are simply read, and the sampling does the debouncing. A switch
    settles in a few milliseconds and is looked at every fifty, so a bounce has
    almost always finished before anything sees it.
    """

    def __init__(self, pins: dict[str, int]) -> None:
        import lgpio

        self._lgpio = lgpio
        self._chip = lgpio.gpiochip_open(0)
        self._pins = dict(pins)
        for pin in self._pins.values():
            lgpio.gpio_claim_input(self._chip, pin, lgpio.SET_PULL_UP)

        self._down = dict.fromkeys(self._pins, False)
        self._shoot_pressed_at: float | None = None
        self.presses: queue.Queue[str] = queue.Queue()

    def polled(self, now: float) -> None:
        """Look at every pin, and put a name down for anything that changed."""
        for name, pin in self._pins.items():
            # Switches go to ground, so pressed reads low.
            pressed = self._lgpio.gpio_read(self._chip, pin) == 0
            if pressed != self._down[name]:
                self._down[name] = pressed
                self._noticed(name, pressed, now)

    def _noticed(self, name: str, pressed: bool, now: float) -> None:
        """What a change means. Only SHOOT cares which way it went.

        The five-way acts on the press, for the feedback. SHOOT waits for the
        release, because until it comes up there is no telling which of its two
        meanings it had.
        """
        if name != "shoot":
            if pressed:
                self.presses.put(name)
            return

        if pressed:
            self._shoot_pressed_at = now
            return

        held_for = now - (self._shoot_pressed_at or now)
        self.presses.put("cancel" if held_for >= HOLD_SECONDS else "shoot")

    def close(self) -> None:
        self._lgpio.gpiochip_close(self._chip)


class Shutter:
    """Opening and closing the camera, and knowing whether it is still open.

    The device times the shot from its own clock, which is the honest source on
    a bulb exposure anyway. This only has to start the camera at the right
    moment, and then tell the difference between a shot that ran its course and
    one that was called off - because those need opposite things doing.
    """

    def __init__(self, camera: Camera) -> None:
        self._camera = camera
        self._running = None
        self._open_for = None

    def opened_for(self, shot) -> None:
        """Open the shutter for a shot whose delay has just run out."""
        if self._open_for is shot:
            return
        self._open_for = shot

        seconds = shot.total_seconds
        if needs_bulb(seconds):
            self._running = self._camera.start_bulb_exposure(seconds)
            return

        # The camera times this one itself, and gphoto2 blocks for as long as it
        # takes - so it waits on a thread of its own rather than stopping the
        # panel and the buttons for half a minute.
        threading.Thread(
            target=self._camera.capture_timed,
            args=(nearest_timed_shutter(seconds),),
            daemon=True,
        ).start()

    def released(self) -> None:
        """The exposure ran its course: leave gphoto2 alone to finish.

        Its last two acts are closing the shutter and waiting for the camera to
        write the frame. Terminating it across those is what leaves a camera
        unreachable at -105, so the handle is simply let go of.
        """
        self._running = None
        self._open_for = None

    def stopped(self) -> None:
        """The shot was called off: take the shutter back."""
        if self._running is not None:
            self._running.cancel()
        self.released()


def synced(device: Device, camera: Camera, panel: Panel, now: float) -> Device:
    """SYNC, with the panel told first.

    Reading the camera shells out to gphoto2 and can take seconds on a Pi Zero,
    during which nothing else happens - so the panel says what it is doing
    before the loop stops answering.
    """
    panel.show(SplashScreen(message="reading camera...", version=""))
    try:
        return device.pressed_sync(camera.read_metered_exposure(), now)
    except CameraError as exc:
        print(f"sync failed: {exc}", file=sys.stderr)
        return device


def applied(device: Device, press: str, camera: Camera, panel: Panel, now: float) -> Device:
    """One press, on the main thread, where everything is decided."""
    if press == "sync":
        return synced(device, camera, panel, now)
    if press == "shoot":
        return device.pressed_shoot(now)
    if press == "cancel":
        # Holding it means "stop": with nothing running there is nothing to
        # stop, and it must not become another way of starting one.
        return device.pressed_shoot(now) if device.shot is not None else device
    return getattr(device, f"pressed_{press}")()


def stepped(device: Device, buttons: Buttons, panel: Panel, camera: Camera,
            shutter: Shutter, now: float) -> Device:
    """One turn of the loop: drain the presses, move the shutter, draw."""
    # Noted before any press can clear it, so that an ending can be told apart
    # from a cancelling afterwards.
    running = device.shot

    buttons.polled(now)
    while not buttons.presses.empty():
        device = applied(device, buttons.presses.get(), camera, panel, now)

    # Before the tick, not after: ticked() ends a shot whose time is up, and a
    # loop that was late - a panel refresh is most of a second - would then find
    # nothing to open the shutter for and skip the exposure entirely.
    shot = device.shot
    if shot is not None and not shot.is_delaying(now):
        shutter.opened_for(shot)

    device = device.ticked(now)

    if running is not None and device.shot is None:
        shutter.released() if running.is_finished(now) else shutter.stopped()

    return device


def run(device: Device, buttons: Buttons, panel: Panel, camera: Camera) -> None:
    """Presses in, frames out, until something asks it to stop.

    The screen is worked out when the device has changed - which a press does,
    and which shows up as a new object, because the device is frozen - or once
    a second otherwise, for the things that move with the clock rather than
    with a button.
    """
    shutter = Shutter(camera)
    drawn_for = None
    drawn_at = 0.0

    while True:
        now = time.monotonic()
        device = stepped(device, buttons, panel, camera, shutter, now)

        if device is not drawn_for or now - drawn_at >= REDRAW_INTERVAL_SECONDS:
            panel.show(device.screen(now))
            drawn_for, drawn_at = device, now

        time.sleep(TICK_SECONDS)


def main() -> int:
    camera = Camera()
    panel = Panel()
    buttons = Buttons(PINS)

    try:
        run(Device(battery=_battery_percent()), buttons, panel, camera)
    except KeyboardInterrupt:
        # systemd stops this with SIGINT for exactly this reason: the panel
        # keeps whatever is on it, so it is left showing the last screen rather
        # than half of one.
        print("stopping", file=sys.stderr)
    finally:
        buttons.close()
        panel.rest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
