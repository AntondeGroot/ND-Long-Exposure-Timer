#!/usr/bin/env python3
"""The device, running on your laptop, with the panel and buttons in a browser.

The Pi's only USB port cannot carry both the camera and an ssh session, and
e-paper takes a second to redraw, so trying the thing out on the hardware is slow
and awkward. Everything except the panel driver and gphoto2 is plain Python, so
it runs here with a browser for the buttons and a PNG for the panel - the frame
served is the exact 122 x 250 buffer the panel would hold.

It runs main.py's own loop rather than a copy of it. The press routing, the
shutter timing, what happens when the camera refuses - all of that is the code
that runs on the Pi, with three stand-ins underneath: buttons that arrive over
HTTP, a panel that remembers its last screen, and a camera that can be unplugged
from the page. A simulator that reimplements the device drifts from it; this one
cannot.

    ./scripts/simulator.py            # then open http://localhost:8000

The camera is faked: the page has the three values SYNC would read off it, so a
scene can be metered without a camera on the desk. The clock is faked too - a
six-minute exposure is worth watching at 60x rather than in real time.
"""

from __future__ import annotations

import argparse
import io
import json
import queue
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from dataclasses import replace  # noqa: E402

import main as runtime  # noqa: E402  (main.py, the loop the Pi runs)
from nd_timer.camera import CameraError, MeteredExposure  # noqa: E402
from nd_timer.device import Device  # noqa: E402
from nd_timer.dial import LADDER_SECONDS  # noqa: E402
from nd_timer.exposure import format_exposure  # noqa: E402
from nd_timer.ui.screens import (  # noqa: E402
    CountdownScreen,
    DelayScreen,
    MainScreen,
    render_countdown,
    render_delay,
    render_main,
)
from nd_timer.ui.settings import SettingsScreen, render_settings  # noqa: E402

PAGE = Path(__file__).resolve().parent / "simulator.html"

RENDERERS = {
    SettingsScreen: render_settings,
    DelayScreen: render_delay,
    CountdownScreen: render_countdown,
    MainScreen: render_main,
}

# Where the gauge starts. Not the unknown the device defaults to: that is right
# on a Pi with nothing answering on the bus, but here it would only look broken.
SIMULATED_BATTERY = 85

# What the fake camera can be set to. The shutter speeds are the camera's own
# ladder, plus the fast end a metered scene in daylight actually lands on.
SHUTTER_CHOICES = (1 / 1000, 1 / 500, 1 / 250, *LADDER_SECONDS)
APERTURE_CHOICES = (1.4, 2.0, 2.8, 4.0, 5.6, 8.0, 11.0, 16.0, 22.0)
ISO_CHOICES = (100, 200, 400, 800, 1600)

DEFAULT_CAMERA = MeteredExposure(iso=100, aperture=11.0, shutter_seconds=1 / 60)

class VirtualClock:
    """Wall-clock time that can be run fast, so a long exposure can be watched.

    A change of speed takes effect from now on: the time already passed is banked
    at the speed it passed at, so speeding up mid-countdown shortens what is left
    rather than jumping the clock.
    """

    def __init__(self) -> None:
        self._speed = 1.0
        self._real = time.monotonic()
        self._virtual = 0.0

    @property
    def virtual(self) -> float:
        """The time as of the last reading, for deciding how fast to run next."""
        return self._virtual

    def now(self, speed: float = 1.0) -> float:
        real = time.monotonic()
        self._virtual += (real - self._real) * self._speed
        self._real = real
        self._speed = speed
        return self._virtual


class FakeCamera:
    """The camera, or the absence of one.

    Unplugging it is a setting here rather than an accident, because what the
    device does when the camera refuses is worth being able to look at: the
    countdown has to not start, and the status bar has to say so.
    """

    def __init__(self) -> None:
        self.metered = DEFAULT_CAMERA
        self.connected = True
        self.doing: str | None = None
        # What gphoto2 would have said. On the Pi this goes to the journal; here
        # the browser is the only place to look, so it is kept for the page.
        self.last_error: str | None = None

    def _refused(self) -> CameraError:
        self.last_error = "Could not detect any camera"
        return CameraError(self.last_error)

    def read_metered_exposure(self) -> MeteredExposure:
        if not self.connected:
            raise self._refused()
        self.last_error = None
        return self.metered

    def start_bulb_exposure(self, seconds: float):
        if not self.connected:
            raise self._refused()
        self.last_error = None
        self.doing = f"bulb, {format_exposure(seconds)}"
        return _RunningExposure(self)

    def capture_timed(self, shutter_value: str) -> None:
        if not self.connected:
            raise self._refused()
        self.last_error = None
        self.doing = f"timed, {shutter_value}"


class _RunningExposure:
    """What start_bulb_exposure hands back: something that can be called off."""

    def __init__(self, camera: FakeCamera) -> None:
        self._camera = camera

    def cancel(self) -> None:
        self._camera.doing = None


class FakeButtons:
    """The five-way, arriving over HTTP instead of down seven wires."""

    def __init__(self) -> None:
        self.presses: queue.Queue[str] = queue.Queue()

    def polled(self, now: float) -> None:
        """Nothing to read: the presses are put here by the web handler."""


class FakePanel:
    """The panel, which here is the last screen it was asked to show."""

    def __init__(self) -> None:
        self.showing = None

    def show(self, screen) -> None:
        self.showing = screen


class Simulator:
    """The device, the fake camera in front of it, and the clock they share.

    It runs main.py's own loop rather than a copy of it. Everything that is not
    hardware - the press routing, the shutter timing, what happens when the
    camera refuses - is then the code that runs on the Pi, and the browser is
    looking at the real thing with three stand-ins underneath it.
    """

    def __init__(self, speed: float) -> None:
        self.device = Device(battery=SIMULATED_BATTERY)
        self.camera = FakeCamera()
        self.buttons = FakeButtons()
        self.panel = FakePanel()
        self.shutter = runtime.Shutter(self.camera)
        self.speed = speed
        self.clock = VirtualClock()
        self._lock = threading.Lock()

    def _now(self) -> float:
        """The clock only runs fast while the shutter is actually open.

        A six-minute exposure is worth watching at 60x. The age of the sync in
        the status bar is not, and would be a lie told sixty times over - and
        neither is the delay before the shutter opens, which at 60x would be
        over before the screen saying so had been read.
        """
        shot = self.device.shot
        open_shutter = shot is not None and not shot.is_delaying(self.clock.virtual)
        return self.clock.now(self.speed if open_shutter else 1.0)

    def pressed(self, button: str) -> None:
        self.buttons.presses.put(button)
        self.stepped()

    def stepped(self) -> None:
        """One turn of the device's own loop, and then the drawing it leaves out.

        run() on the Pi decides when to draw, and skips it unless the device
        changed or a second has passed - which is a CPU concern on an ARMv6 and
        not one here, where a frame is only built when the browser asks for it.
        The panel still has to be set, though: without it the last thing shown
        is whatever synced() put up while it was blocking.
        """
        with self._lock:
            now = self._now()
            self.device = runtime.stepped(
                self.device, self.buttons, self.panel, self.camera, self.shutter, now
            )
            self.panel.show(self.device.screen(now))

    def set_camera(self, iso: float, aperture: float, shutter: float, connected: bool) -> None:
        with self._lock:
            self.camera.metered = MeteredExposure(
                iso=iso, aperture=aperture, shutter_seconds=shutter
            )
            self.camera.connected = connected

    def set_battery(self, percent: int | None, charging: bool) -> None:
        """Stand in for the UPS, which is not on the desk with the browser.

        There is no INA219 here, so the gauge is set by hand instead of read.
        It is worth having: the hatched unknown, a flat cell and the charging
        bolt are three things the status bar draws that are otherwise only
        visible by unplugging hardware.
        """
        with self._lock:
            self.device = replace(self.device, battery=percent, charging=charging)
            self.panel.show(self.device.screen(self._now()))

    def set_speed(self, speed: float) -> None:
        with self._lock:
            self.speed = speed

    def frame(self) -> bytes:
        """The panel's current contents, as the PNG the browser shows."""
        self.stepped()
        screen = self.panel.showing
        if screen is None:
            screen = self.device.screen(self._now())

        image = RENDERERS[type(screen)](screen)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def state(self) -> dict:
        """What the page needs that the picture does not say."""
        with self._lock:
            device = self.device
            return {
                "shooting": device.shot is not None,
                "camera": {
                    "iso": self.camera.metered.iso,
                    "aperture": self.camera.metered.aperture,
                    "shutter": self.camera.metered.shutter_seconds,
                    "connected": self.camera.connected,
                },
                "battery": {"percent": device.battery, "charging": device.charging},
                "doing": self.camera.doing,
                "fault": device.fault,
                "error": self.camera.last_error,
                "choices": {
                    "iso": [[iso, f"{iso:g}"] for iso in ISO_CHOICES],
                    "aperture": [[f, f"f/{f:g}"] for f in APERTURE_CHOICES],
                    "shutter": [[s, format_exposure(s)] for s in SHUTTER_CHOICES],
                },
            }


class Handler(BaseHTTPRequestHandler):
    simulator: Simulator

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/":
            self._send(PAGE.read_bytes(), "text/html; charset=utf-8")
        elif route == "/frame.png":
            self._send(self.simulator.frame(), "image/png")
        elif route == "/state":
            self._send_json(self.simulator.state())
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)
        if route == "/press":
            self.simulator.pressed(query.get("button", [""])[0])
        elif route == "/camera":
            self.simulator.set_camera(
                iso=float(query["iso"][0]),
                aperture=float(query["aperture"][0]),
                shutter=float(query["shutter"][0]),
                connected=query.get("connected", ["1"])[0] == "1",
            )
        elif route == "/battery":
            level = query.get("percent", [""])[0]
            self.simulator.set_battery(
                percent=int(level) if level else None,
                charging=query.get("charging", ["0"])[0] == "1",
            )
        elif route == "/speed":
            self.simulator.set_speed(float(query["speed"][0]))
        else:
            return self.send_error(404)
        self._send_json(self.simulator.state())

    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict) -> None:
        self._send(json.dumps(payload).encode(), "application/json")

    def log_message(self, *_args) -> None:
        """Quiet: a press a second would otherwise fill the terminal."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--speed", type=float, default=60.0,
                        help="how fast the clock runs while an exposure is open")
    parser.add_argument("--no-browser", action="store_true")
    arguments = parser.parse_args()

    Handler.simulator = Simulator(arguments.speed)
    server = ThreadingHTTPServer(("127.0.0.1", arguments.port), Handler)

    address = f"http://localhost:{arguments.port}"
    print(f"ND Long Exposure Timer simulator on {address}  (ctrl-c to stop)")
    if not arguments.no_browser:
        webbrowser.open(address)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
