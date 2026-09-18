"""Exposure arithmetic for shooting through neutral-density filters.

The device asks it backwards - I want to expose for this long, so what do I put
on the lens? - but the arithmetic is the same either way, and two rules do all
the work.

Reciprocity: a stop gained on ISO or aperture is a stop given back on shutter, so
the exposure stays correct while the photographer trades one for another.

Filtration: every stop of ND doubles the time. Ten stops is a factor of 1024,
which is the sum the device exists to do for you in the dark.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600

# The longest exposure the camera can time itself; past this the Pi holds the
# shutter open on bulb and becomes the timer.
LONGEST_TIMED_EXPOSURE_SECONDS = 30.0

# Fast shutter speeds are read as fractions, the way they are printed on the
# dial: "1/125 s", not "0.008 s". The camera itself switches to decimals at 0.4.
FRACTIONS_BELOW_SECONDS = 0.4

# Past ten seconds a tenth of a second is noise: nothing about the shot changes
# between 12.3s and 12.4s, and the two extra glyphs cost the hero its size.
TENTHS_SHOWN_BELOW_SECONDS = 10.0

# Stacking more than this is possible but not useful: vignetting and colour cast
# make the result worse than the extra stops are worth.
MAX_STACKED_FILTERS = 3


@dataclass(frozen=True)
class NdFilter:
    """A filter, named the way it is printed on the ring."""

    name: str
    stops: float

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class FilterChoice:
    """One selectable entry in the ND list: a filter, a stack, or nothing at all."""

    filters: tuple[NdFilter, ...]
    stops: float

    @property
    def label(self) -> str:
        if not self.filters:
            return "none"
        return " + ".join(f.name for f in self.filters)

    @property
    def short_label(self) -> str:
        """The label for a 122px row, which is sitting under a heading of "ND".

        "ND8 + ND64 + ND1000" becomes "8+64+1000": the row already says these are
        ND filters, and the numbers are what tell them apart.
        """
        if not self.filters:
            return "none"
        return "+".join(f.name.removeprefix("ND") for f in self.filters)

    @property
    def stops_label(self) -> str:
        """Stops, written the short way: "13st"."""
        return f"{self.stops:g}st"

    def __str__(self) -> str:
        return self.label


# Stop values are the honest ones: ND100 and ND400 are sold as round numbers but
# are not powers of two, and rounding them loses most of a stop.
COMMON_FILTERS = (
    NdFilter("ND2", 1.0),
    NdFilter("ND4", 2.0),
    NdFilter("ND8", 3.0),
    NdFilter("ND16", 4.0),
    NdFilter("ND32", 5.0),
    NdFilter("ND64", 6.0),
    NdFilter("ND100", 6.64),
    NdFilter("ND400", 8.64),
    NdFilter("ND1000", 10.0),
    NdFilter("ND32000", 15.0),
    NdFilter("ND100.000", 16.6),
    NdFilter("ND1.000.000", 20.0),
)


def stops_between(base: float, adjusted: float) -> float:
    """How many stops brighter `adjusted` is than `base`, for ISO-like quantities."""
    return math.log2(adjusted / base)


def shutter_after_shift(
    metered_shutter: float,
    metered_iso: float,
    metered_aperture: float,
    working_iso: float,
    working_aperture: float,
) -> float:
    """The base shutter once ISO or aperture has been moved off the metered values.

    A stop of extra light from ISO or aperture is a stop taken off the shutter, so
    the exposure stays the one the meter chose. Aperture counts double because
    f-numbers are a square-root scale.
    """
    iso_stops = stops_between(metered_iso, working_iso)
    aperture_stops = 2 * stops_between(working_aperture, metered_aperture)
    return metered_shutter / (2.0 ** (iso_stops + aperture_stops))


def exposure_through_filter(base_seconds: float, stops: float) -> float:
    """The exposure needed once the filter is on: each stop doubles the time."""
    if base_seconds <= 0:
        raise ValueError(f"base exposure must be positive, got {base_seconds}")
    return base_seconds * (2.0**stops)


def format_exposure(seconds: float) -> str:
    """The exposure written the way it is read off the panel.

    Precision follows length: a fast shutter wants to be a fraction, a second and
    a bit wants its tenth, a minute wants its seconds, an hour wants neither.
    """
    if seconds < FRACTIONS_BELOW_SECONDS:
        return f"1/{round(1 / seconds)} s"
    if seconds < TENTHS_SHOWN_BELOW_SECONDS:
        return f"{seconds:.1f} s"

    whole = round(seconds)
    if whole < SECONDS_PER_MINUTE:
        return f"{whole} s"
    if whole < SECONDS_PER_HOUR:
        return _written_in_minutes(whole)
    return _written_in_hours(whole)


def _written_in_minutes(whole_seconds: int) -> str:
    minutes, seconds = divmod(whole_seconds, SECONDS_PER_MINUTE)
    return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"


def _written_in_hours(whole_seconds: int) -> str:
    hours, remainder = divmod(whole_seconds, SECONDS_PER_HOUR)
    minutes = remainder // SECONDS_PER_MINUTE
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def needs_bulb(seconds: float) -> bool:
    """Whether this exposure is too long for the camera to time itself."""
    return seconds > LONGEST_TIMED_EXPOSURE_SECONDS


def filter_choices(owned: tuple[NdFilter, ...]) -> tuple[FilterChoice, ...]:
    """Every usable combination of the owned filters, as one sorted list.

    Presenting stacks as their own entries turns ND from two decisions (which
    filters, in what combination) into one scrollable value, which is the only
    thing a left/right pair of buttons can express.
    """
    choices = {0.0: FilterChoice((), 0.0)}
    for size in range(1, min(len(owned), MAX_STACKED_FILTERS) + 1):
        for stack in combinations(owned, size):
            total = round(sum(f.stops for f in stack), 2)
            # Different stacks can land on the same stops; the first one wins,
            # and it is the one using fewest filters because sizes ascend.
            choices.setdefault(total, FilterChoice(stack, total))
    return tuple(choices[stops] for stops in sorted(choices))
