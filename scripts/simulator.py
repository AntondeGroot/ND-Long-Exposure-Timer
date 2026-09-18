#!/usr/bin/env python3
"""The device, running on your laptop, with the panel and buttons in a browser.

The Pi's only USB port cannot carry both the camera and an ssh session, and
e-paper takes a second to redraw, so trying the thing out on the hardware is slow
and awkward. Everything except the panel driver and gphoto2 is plain Python, so
the same state machine runs here with a browser for the buttons and a PNG for the
panel - the frame served is the exact 122 x 250 buffer the panel would hold.

    ./scripts/simulator.py            # then open http://localhost:8000

The camera is faked: the page has the three values SYNC would read off it, so a
scene can be metered without a camera on the desk. The clock is faked too - a
six-minute exposure is worth watching at 60x rather than in real time.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nd_timer.camera import MeteredExposure  # noqa: E402
from nd_timer.device import Device  # noqa: E402
from nd_timer.dial import LADDER_SECONDS  # noqa: E402
from nd_timer.exposure import format_exposure  # noqa: E402
from nd_timer.ui.screens import CountdownScreen, MainScreen, render_countdown, render_main  # noqa: E402
from nd_timer.ui.settings import SettingsScreen, render_settings  # noqa: E402

PAGE = Path(__file__).resolve().parent / "simulator.html"

RENDERERS = {
    SettingsScreen: render_settings,
    CountdownScreen: render_countdown,
    MainScreen: render_main,
}

# What the fake camera can be set to. The shutter speeds are the camera's own
# ladder, plus the fast end a metered scene in daylight actually lands on.
SHUTTER_CHOICES = (1 / 1000, 1 / 500, 1 / 250, *LADDER_SECONDS)
APERTURE_CHOICES = (1.4, 2.0, 2.8, 4.0, 5.6, 8.0, 11.0, 16.0, 22.0)
ISO_CHOICES = (100, 200, 400, 800, 1600)

DEFAULT_CAMERA = MeteredExposure(iso=100, aperture=11.0, shutter_seconds=1 / 60)

PRESSES = {
    "up": lambda device, _: device.pressed_up(),
    "down": lambda device, _: device.pressed_down(),
    "left": lambda device, _: device.pressed_left(),
    "right": lambda device, _: device.pressed_right(),
    "centre": lambda device, _: device.pressed_centre(),
}


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

    def now(self, speed: float = 1.0) -> float:
        real = time.monotonic()
        self._virtual += (real - self._real) * self._speed
        self._real = real
        self._speed = speed
        return self._virtual


class Simulator:
    """The device, the fake camera in front of it, and the clock they share."""

    def __init__(self, speed: float) -> None:
        self.device = Device()
        self.camera = DEFAULT_CAMERA
        self.speed = speed
        self.clock = VirtualClock()
        self._lock = threading.Lock()

    def _now(self) -> float:
        """The clock only runs fast while the shutter is open.

        A six-minute exposure is worth watching at 60x; the age of the sync in
        the status bar is not, and would be a lie told sixty times over.
        """
        return self.clock.now(self.speed if self.device.shot is not None else 1.0)

    def pressed(self, button: str) -> None:
        with self._lock:
            now = self._now()
            if button == "sync":
                self.device = self.device.pressed_sync(self.camera, now)
            elif button == "shoot":
                self.device = self.device.pressed_shoot(now)
            elif button in PRESSES:
                self.device = PRESSES[button](self.device, now)

    def set_camera(self, iso: float, aperture: float, shutter: float) -> None:
        with self._lock:
            self.camera = MeteredExposure(iso=iso, aperture=aperture, shutter_seconds=shutter)

    def set_speed(self, speed: float) -> None:
        with self._lock:
            self.speed = speed

    def frame(self) -> bytes:
        """The panel's current contents, as the PNG the browser shows."""
        with self._lock:
            now = self._now()
            self.device = self.device.ticked(now)
            screen = self.device.screen(now)

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
                    "iso": self.camera.iso,
                    "aperture": self.camera.aperture,
                    "shutter": self.camera.shutter_seconds,
                },
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
