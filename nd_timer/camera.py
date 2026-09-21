"""Talking to the camera through gphoto2.

One rule governs everything here: a gphoto2 process opens a PTP session on start
and closes it on exit, and the camera will not tolerate that session being torn
down mid-operation. Opening the shutter in one process and closing it in another
leaves the camera unreachable ("Could not detect any camera", -105), and settings
made in one process are simply not in force in the next.

So every operation is exactly one invocation, with its actions chained.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass

GPHOTO2 = "gphoto2"

# Long enough for a Pi Zero to walk the camera's config tree, short enough that a
# missing camera does not hang the UI.
READ_TIMEOUT_SECONDS = 45

# Settling time after the shutter closes, for the camera to finish writing.
POST_EXPOSURE_SETTLE_SECONDS = 3


class CameraError(RuntimeError):
    """The camera could not be reached or did not do what was asked."""


@dataclass(frozen=True)
class MeteredExposure:
    """What the camera's meter had chosen when SYNC was pressed."""

    iso: float
    aperture: float
    shutter_seconds: float


# The speeds a camera will time itself, in thirds, as it prints them. It runs
# three rungs past nd_timer.dial's ladder: that one stops at 15s because the
# device's own dial becomes a clock after it, but the camera keeps going to 30
# before bulb is the only option left. Snapping to the wrong end of that gap is
# most of a stop.
TIMED_SHUTTERS = (
    1 / 125, 1 / 100, 1 / 80, 1 / 60, 1 / 50, 1 / 40, 1 / 30, 1 / 25,
    1 / 20, 1 / 15, 1 / 13, 1 / 10, 1 / 8, 1 / 6, 1 / 5, 1 / 4, 1 / 3,
    0.4, 0.5, 0.6, 0.8,
    1.0, 1.3, 1.6, 2.0, 2.5, 3.2,
    4.0, 5.0, 6.0, 8.0, 10.0, 13.0, 15.0, 20.0, 25.0, 30.0,
)


def nearest_timed_shutter(seconds: float) -> str:
    """The nearest speed the camera can be set to, written the way it writes it.

    gphoto2 will only accept one of the camera's own choices, so the exposure
    arithmetic's exact answer has to be snapped to a rung before it is sent.
    Fractions have no unit on the dial: "1/60", not "1/60 s".
    """
    nearest = min(TIMED_SHUTTERS, key=lambda rung: abs(rung - seconds))
    if nearest >= 1:
        return f"{round(nearest)}"
    return f"1/{round(1 / nearest)}"


def parse_shutter_speed(text: str) -> float:
    """Read a shutter speed the way a camera writes it, in seconds.

    Cameras report "1/250" for fractions and "30" for whole seconds. "Bulb" and
    "Time" are settings rather than durations, so they are rejected here and the
    caller decides what to do about it.
    """
    cleaned = text.strip().rstrip("s").strip()
    if not cleaned:
        raise ValueError("empty shutter speed")

    if "/" in cleaned:
        numerator, _, denominator = cleaned.partition("/")
        try:
            return float(numerator) / float(denominator)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(f"cannot read shutter speed {text!r}") from exc

    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"cannot read shutter speed {text!r}") from exc


def parse_aperture(text: str) -> float:
    """Read an f-number, written variously as "11", "f/11" or "f11"."""
    cleaned = text.strip().lstrip("fF").lstrip("/").strip()
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"cannot read aperture {text!r}") from exc


def current_values(gphoto_output: str) -> list[str]:
    """The `Current:` value from each config block, in the order they were asked for."""
    return [
        line.partition(":")[2].strip()
        for line in gphoto_output.splitlines()
        if line.startswith("Current:")
    ]


class Camera:
    """The camera on the other end of the USB cable."""

    def __init__(self, runner=subprocess.run, popen=subprocess.Popen) -> None:
        # Injected so the application can be developed and tested without a
        # camera, which matters here: the USB port cannot carry ssh and the
        # camera at the same time, so the camera is absent during development.
        self._run = runner
        self._popen = popen

    def is_connected(self) -> bool:
        detected = self._capture(["--auto-detect"], timeout=20)
        # The first two lines are the header and its underline.
        return any(line.strip() for line in detected.splitlines()[2:])

    def read_metered_exposure(self) -> MeteredExposure:
        """What SYNC fetches: the camera's current settings, in one invocation.

        Three separate gphoto2 calls would mean three PTP sessions - several
        seconds each on a Pi Zero, for no benefit.
        """
        output = self._capture(
            [
                "--get-config", "iso",
                "--get-config", "aperture",
                "--get-config", "shutterspeed",
            ],
            timeout=READ_TIMEOUT_SECONDS,
        )

        values = current_values(output)
        if len(values) != 3:
            raise CameraError(
                f"expected iso, aperture and shutter speed, got {len(values)} values"
            )

        raw_iso, raw_aperture, raw_shutter = values
        try:
            return MeteredExposure(
                iso=float(raw_iso),
                aperture=parse_aperture(raw_aperture),
                shutter_seconds=parse_shutter_speed(raw_shutter),
            )
        except ValueError as exc:
            # Bulb is the usual cause: the camera is already set up for a long
            # exposure, so there is no metered shutter speed to read.
            raise CameraError(f"camera reported {values}: {exc}") from exc

    def start_bulb_exposure(self, seconds: float) -> RunningExposure:
        """Open the shutter for `seconds`, returning while it is still open."""
        process = self._popen(
            [GPHOTO2, *_bulb_arguments(seconds)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return RunningExposure(process, seconds)

    def capture_timed(self, shutter_value: str) -> None:
        """Take a shot the camera times itself, for anything within its 30s limit.

        `shutter_value` is one of the camera's own choices, e.g. "1/60" or "25" -
        the arithmetic's exact answer has to be snapped to the dial first.
        """
        self._capture(
            [
                "--set-config", "capturetarget=1",
                "--set-config", f"shutterspeed={shutter_value}",
                "--trigger-capture",
            ],
            timeout=READ_TIMEOUT_SECONDS,
        )

    def _capture(self, arguments: list[str], timeout: int) -> str:
        try:
            result = self._run(
                [GPHOTO2, *arguments],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise CameraError(f"gphoto2 did not answer within {timeout}s") from exc
        except FileNotFoundError as exc:
            raise CameraError("gphoto2 is not installed") from exc

        if result.returncode != 0:
            raise CameraError(_first_error_line(result.stderr or result.stdout))
        return result.stdout


def _first_error_line(output: str) -> str:
    """gphoto2's errors are buried in a wall of debugging advice; take the first."""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("***"):
            return stripped
    return "gphoto2 failed"


class RunningExposure:
    """A shutter that is currently open, and the clock the UI counts down from.

    The gphoto2 process blocks for the whole exposure, so it runs in the
    background and this reports progress from our own clock. That is the honest
    source anyway: the Pi is the timer on a bulb shot.
    """

    def __init__(self, process, total_seconds: float, clock=time.monotonic) -> None:
        self._process = process
        self._clock = clock
        self._started_at = clock()
        self.total_seconds = total_seconds

    @property
    def elapsed_seconds(self) -> float:
        return self._clock() - self._started_at

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.total_seconds - self.elapsed_seconds)

    @property
    def progress(self) -> float:
        """How far through, from 0 to 1, for the progress bar."""
        if self.total_seconds <= 0:
            return 1.0
        return min(1.0, self.elapsed_seconds / self.total_seconds)

    def is_running(self) -> bool:
        return self._process.poll() is None

    def cancel(self) -> None:
        """Abort the shot. Terminating gphoto2 closes the session and the shutter."""
        if self.is_running():
            self._process.terminate()

    def wait(self) -> None:
        """Block until the exposure finishes, raising if gphoto2 failed."""
        _, stderr = self._process.communicate()
        if self._process.returncode != 0:
            raise CameraError(_first_error_line(stderr or ""))


def _bulb_arguments(seconds: float) -> list[str]:
    """The one invocation that takes a bulb exposure.

    Every part of this has to be in the same process: capturetarget is a session
    setting rather than something the camera remembers, and splitting the open
    from the close tears down the session while the shutter is open.
    """
    return [
        "--set-config", "capturetarget=1",   # keep the frame on the camera's card
        "--set-config", "bulb=1",            # open
        "--wait-event", f"{int(round(seconds))}s",
        "--set-config", "bulb=0",            # close
        "--wait-event", f"{POST_EXPOSURE_SETTLE_SECONDS}s",
    ]
