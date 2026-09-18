"""Setting the exposure time, which is the one thing the photographer chooses.

Everything else on the panel is worked back from this: the device is in shutter
priority, and this is the shutter. A scenario puts a time here to start from -
CLOUDS wants minutes, waves want a fraction of a second - and from there it is
dialled, because the light is moving, or the scene is known, or the suggestion
is close but not it.

One press of the five-way's centre on the time starts setting it, another stops.
While it is being set the four directions do the work, and they have to cover
everything from 1/125s to an hour, which is nineteen stops:

  left / right  walks a ladder whose rungs grow with the number - thirds of a
                stop while the time is in seconds, whole minutes once it is not
  up / down     moves one second, for landing on a time the ladder skips

A hand-set time stays until a scenario is chosen, which is the photographer
asking for that scenario's time instead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from nd_timer.exposure import SECONDS_PER_MINUTE, format_exposure

# The camera's own third-stop shutter ladder, which is what the photographer's
# thumb already expects the steps to feel like.
#
# It runs down to 1/125 rather than stopping where long exposure stops. Waves
# want 1/8 and the fast end costs nothing to carry, and a dial that reaches
# 1/125 is a dial a self-timer can be built on later - a countdown to a shutter
# the camera times itself is the same dial with a different button on the end.
#
# The top rung is 15s because the next speed the camera offers is 20s, and the
# minute region reads better starting from 16.
LADDER_SECONDS = (
    1 / 125, 1 / 100, 1 / 80, 1 / 60, 1 / 50, 1 / 40, 1 / 30, 1 / 25,
    1 / 20, 1 / 15, 1 / 13, 1 / 10, 1 / 8, 1 / 6, 1 / 5, 1 / 4, 1 / 3,
    0.4, 0.5, 0.6, 0.8,
    1.0, 1.3, 1.6, 2.0, 2.5, 3.2,
    4.0, 5.0, 6.0, 8.0, 10.0, 13.0, 15.0,
)

SHORTEST_SECONDS = LADDER_SECONDS[0]
LONGEST_RUNG_SECONDS = LADDER_SECONDS[-1]

# The bottom of the minute region, and the first time written as mm:ss. Past the
# ladder a third of a stop is a rounder number than anyone is dialling for, so
# the steps become whole minutes and the display becomes a clock.
FIRST_MINUTE_REGION_SECONDS = 16.0

# An hour is as long as the battery, the sensor and the photographer's patience
# all hold out, and it is where mm:ss stops being a sensible way to write a time.
LONGEST_SECONDS = 60 * SECONDS_PER_MINUTE

# What up and down move. One second is the finest thing worth asking for: below
# that the shutter's own latency is the bigger error.
NUDGE_SECONDS = 1.0

# Where a second stops reading as an adjustment. Up and down keep working below
# this - a second is often exactly how you leave the fast end - but a screen
# offering "1s" beside 1/8 would be offering a jump of three stops as if it were
# a nudge, so it says nothing there and lets the ladder speak for itself.
FINE_ADJUSTMENT_FROM_SECONDS = 1.0


def longer(seconds: float) -> float:
    """The next time up: a rung while in seconds, the next whole minute after."""
    if seconds < LONGEST_RUNG_SECONDS:
        return _within_limits(_rung_above(seconds))
    if seconds < FIRST_MINUTE_REGION_SECONDS:
        return FIRST_MINUTE_REGION_SECONDS
    return _within_limits(_next_whole_minute(seconds))


def shorter(seconds: float) -> float:
    """The next time down, which is `longer` read backwards.

    The minute region is left only from its bottom rung: rounding 40s down to a
    whole minute would be zero, so it lands on 00:16 and the ladder takes over.
    """
    if seconds <= FIRST_MINUTE_REGION_SECONDS:
        return _within_limits(_rung_below(seconds))
    return max(_previous_whole_minute(seconds), FIRST_MINUTE_REGION_SECONDS)


def is_fine_adjustment(seconds: float) -> bool:
    """Whether a second on or off reads as an adjustment rather than a jump.

    It never stops a press: this is what the screen offers, not what it does.
    """
    return seconds >= FINE_ADJUSTMENT_FROM_SECONDS


def nudged(seconds: float, direction: int) -> float:
    """One second on or off, for the times that sit between the rungs."""
    return _within_limits(seconds + direction * NUDGE_SECONDS)


def dialled_label(seconds: float) -> str:
    """The time as it reads while it is being set.

    Seconds are written as the rest of the device writes them. Past the ladder it
    becomes a clock: mm:ss holds its shape as the digits change, so a second on
    or off is a digit moving rather than the whole number reflowing.
    """
    if seconds < FIRST_MINUTE_REGION_SECONDS:
        return format_exposure(seconds)

    minutes, remainder = divmod(round(seconds), SECONDS_PER_MINUTE)
    return f"{minutes:02d}:{remainder:02d}"


def _rung_above(seconds: float) -> float:
    return next((rung for rung in LADDER_SECONDS if rung > seconds), LONGEST_RUNG_SECONDS)


def _rung_below(seconds: float) -> float:
    return next((rung for rung in reversed(LADDER_SECONDS) if rung < seconds), SHORTEST_SECONDS)


def _next_whole_minute(seconds: float) -> float:
    whole_minutes = int(seconds // SECONDS_PER_MINUTE)
    return (whole_minutes + 1) * SECONDS_PER_MINUTE


def _previous_whole_minute(seconds: float) -> float:
    whole_minutes = math.ceil(seconds / SECONDS_PER_MINUTE)
    return (whole_minutes - 1) * SECONDS_PER_MINUTE


def _within_limits(seconds: float) -> float:
    """Every press lands inside the dial's own range, wherever it started.

    A calculated answer can be faster than the ladder's floor - a metered scene
    with no filter on it - and the first press pulls it up to 1/125, which is as
    fast as anything the Pi is going to be asked to time.
    """
    return min(max(seconds, SHORTEST_SECONDS), LONGEST_SECONDS)


@dataclass(frozen=True)
class Dial:
    """The exposure time on screen, and whether the photographer put it there.

    The presses arrive here already routed: the screen decides that the time is
    what the five-way is pointing at, and this decides what each direction means.
    Presses that arrive while the time is not being set are ignored rather than
    guessed at, so nothing changes the exposure without the centre press first.
    """

    seconds: float
    is_hand_set: bool = False
    is_being_set: bool = False

    @property
    def shows_nudge_hint(self) -> bool:
        """Whether the screen says a second is a press away. It always is."""
        return is_fine_adjustment(self.seconds)

    @property
    def label(self) -> str:
        return dialled_label(self.seconds) if self.is_being_set else format_exposure(self.seconds)

    def pressed_centre(self) -> Dial:
        """Start setting the time, or stop."""
        return replace(self, is_being_set=not self.is_being_set)

    def pressed_right(self) -> Dial:
        return self._moved_to(longer(self.seconds))

    def pressed_left(self) -> Dial:
        return self._moved_to(shorter(self.seconds))

    def pressed_up(self) -> Dial:
        return self._moved_to(nudged(self.seconds, 1))

    def pressed_down(self) -> Dial:
        return self._moved_to(nudged(self.seconds, -1))

    def suggested(self, seconds: float) -> Dial:
        """A time the device put here rather than the thumb: a scenario's own.

        It is not hand-set, so the screen stops saying SET - the time on the
        panel is the one the scenario asks for until it is dialled again.
        """
        return Dial(seconds)

    def _moved_to(self, seconds: float) -> Dial:
        if not self.is_being_set:
            return self
        return replace(self, seconds=seconds, is_hand_set=True)
