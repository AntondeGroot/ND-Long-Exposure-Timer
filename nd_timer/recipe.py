"""Working backwards from the time you want to the camera that would give it.

Shutter priority, with one more variable than a camera has. You choose the
exposure time; everything else is the device's to solve. A camera in that mode
has only the aperture to balance with, so it runs out fast - this has the filters
too, and each stop of ND doubles the time without touching the picture at all.

That makes ND the coarse control and the camera the trim:

  filters  3, 6, 10 stops at a time, and free: they cost nothing but glass
  aperture a stop at a time, but it is the one that changes the photograph, so
           it is moved last and least
  ISO      thirds of a stop, which is what turns "nearly" into "exactly"

The search is over three ladders at once, so it is not run as three loops. For
each ISO and aperture the filtration needed is arithmetic, and the bag is sorted
by stops, so the nearest stack is a bisection rather than a scan.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass

from nd_timer.exposure import FilterChoice, exposure_through_filter, shutter_after_shift

# The ISOs a camera actually offers, in thirds. Anything past the user's ceiling
# is never considered, however well it would fit.
STANDARD_ISOS = (100, 125, 160, 200, 250, 320, 400, 500, 640, 800, 1000, 1250, 1600)

# Thirds, written the way the camera prints them - f/6.3 rather than the 6.35 it
# really is, because what matters is that the number can be dialled in. Lenses
# end on these too: an f/3.5-6.3 zoom has no whole stop to call its own.
#
# That the aperture is the one choice the photograph itself can see is not a
# reason to give it coarse steps - it is a reason to move it last, which the
# ranking does. A finer ladder only means that when it must move, it moves less.
#
# Which of these a given lens actually has is a setting, because no lens has all
# of them: the ends are named by their f-numbers, so the lowest is the widest.
APERTURES = (
    1.4, 1.6, 1.8, 2.0, 2.2, 2.5, 2.8, 3.2, 3.5,
    4.0, 4.5, 5.0, 5.6, 6.3, 7.1, 8.0, 9.0, 10.0,
    11.0, 13.0, 14.0, 16.0, 18.0, 20.0, 22.0,
)

# Three thresholds, in stops, for three different questions.
#
# A third of a stop is the finest step the camera's own ISO ladder offers, so a
# recipe inside it has landed on the time as far as the camera is concerned.
# Nothing closer than that is worth spending a filter or depth of field on.
MATCHED_WITHIN_STOPS = 1 / 3

# Half a step either side is therefore as near as anything can be set, and the
# solver stops paying to close a miss smaller than it: there is no correction
# left that would close it.
CLOSEST_SETTABLE_STOPS = MATCHED_WITHIN_STOPS / 2

# What the screen calls exact is a different question - not "could this be
# closer" but "is there anything here worth reading". Two times a tenth of a
# stop apart share one recipe, because nothing on the camera can tell them
# apart, but they are not the same exposure: the second is a minute more of
# cloud. A row that called both of them exact would be answering the first
# question while the eye was asking the second.
EXACT_WITHIN_STOPS = 0.05

# What a recipe costs, counted in stops so that the four things it can spend are
# comparable. They are not worth the same.
#
# A stop of aperture is worth two stops of ISO, because it changes what the
# photograph is rather than how clean it is. A stop of missed exposure is worth
# more than either, because it is the only one of the four that lands in the
# file whatever is done afterwards. A filter is priced like a stop of aperture:
# it costs vignetting, colour cast and two more surfaces to flare, which is
# real, but not so much that the device should send a photographer from f/6.3 to
# f/22 to avoid screwing on a second one.
#
# ISO is priced by how far above the bottom of the ladder it sits rather than by
# how far it has moved: the noise is in the number itself, and a long exposure on
# a tripod wants base ISO whatever the camera happened to be set to when it was
# metered.
MISS_WEIGHT = 5
APERTURE_WEIGHT = 2
ISO_WEIGHT = 1
FILTER_WEIGHT = 2


@dataclass(frozen=True)
class Recipe:
    """What to put on the lens and set on the camera for the time you asked for.

    The shutter the camera metered is not in here, because a recipe never moves
    it: it is the reading everything is measured against, and it stays whatever
    SYNC saw until SYNC is pressed again. `iso` and `aperture` are the settings
    to dial in, and `achieved_seconds` is the exposure they and the filters
    actually come to.

    `error_stops` is what the shot costs if the wanted time is used anyway:
    positive is brighter than metered, negative is darker. It is not always zero
    and the device does not pretend otherwise - with a bag that cannot reach, a
    camera in shutter priority blinks its aperture and takes the shot.

    It is not the same question as whether the recipe could have been closer.
    One recipe serves every time within a third of a stop of it, because nothing
    on the camera can be set finely enough to tell those times apart; the error
    is what says which of them this one is.
    """

    filters: FilterChoice
    iso: float
    aperture: float
    wanted_seconds: float
    achieved_seconds: float
    error_stops: float

    @property
    def is_matched(self) -> bool:
        return abs(self.error_stops) <= MATCHED_WITHIN_STOPS

    @property
    def is_as_close_as_settable(self) -> bool:
        """Whether any change to the camera could bring it closer to the time."""
        return abs(self.error_stops) <= CLOSEST_SETTABLE_STOPS

    @property
    def is_exact(self) -> bool:
        """Whether the miss is too small to be worth a row of its own."""
        return abs(self.error_stops) <= EXACT_WITHIN_STOPS

    @property
    def error_label(self) -> str:
        """The miss, as the row under ND prints it: "exact", "+0.3st", "-3st"."""
        if self.is_exact:
            return "exact"
        return f"{self.error_stops:+.1f}st"


def recipe_for(
    wanted_seconds: float,
    metered_shutter: float,
    metered_iso: float,
    metered_aperture: float,
    choices: tuple[FilterChoice, ...],
    highest_iso: float = 400,
    lowest_aperture: float = APERTURES[0],
    highest_aperture: float = APERTURES[-1],
) -> Recipe:
    """The closest the bag and the camera can come to exposing for `wanted_seconds`.

    Among everything that lands within a third of a stop the cheapest one wins,
    and cheap is counted in what it costs the photograph: the glass in front of
    the lens, the depth of field it was framed at, and the ISO it was metered
    at, all priced in stops so that they can be weighed against each other.

    The ISO ceiling and the two ends of the aperture are the photographer's own
    limits - the noise they will accept and the lens they actually own - so they
    bound the search rather than being traded against how well a recipe fits.
    """
    isos = [iso for iso in STANDARD_ISOS if iso <= highest_iso] or [metered_iso]
    apertures = [f for f in APERTURES if lowest_aperture <= f <= highest_aperture] or [metered_aperture]

    best = None
    best_rank = None
    for aperture in apertures:
        for iso in isos:
            candidate = _best_filtration(
                wanted_seconds, metered_shutter, metered_iso, metered_aperture,
                choices, iso, aperture,
            )
            rank = _rank(candidate, metered_aperture)
            if best_rank is None or rank < best_rank:
                best, best_rank = candidate, rank

    return best


def _best_filtration(
    wanted_seconds: float,
    metered_shutter: float,
    metered_iso: float,
    metered_aperture: float,
    choices: tuple[FilterChoice, ...],
    iso: float,
    aperture: float,
) -> Recipe:
    """The stack nearest to what this ISO and aperture still need, by bisection.

    The shift is arithmetic on the metered reading rather than a change to it:
    this is the exposure that reading comes to once ISO and aperture have moved,
    and it exists only to say how much filtration is left to find.
    """
    unfiltered = shutter_after_shift(
        metered_shutter=metered_shutter,
        metered_iso=metered_iso,
        metered_aperture=metered_aperture,
        working_iso=iso,
        working_aperture=aperture,
    )
    wanted_stops = math.log2(wanted_seconds / unfiltered)
    choice = _nearest_choice(choices, wanted_stops)

    achieved = exposure_through_filter(unfiltered, choice.stops)
    return Recipe(
        filters=choice,
        iso=iso,
        aperture=aperture,
        wanted_seconds=wanted_seconds,
        achieved_seconds=achieved,
        error_stops=math.log2(wanted_seconds / achieved),
    )


def _nearest_choice(choices: tuple[FilterChoice, ...], wanted_stops: float) -> FilterChoice:
    """The stack closest to `wanted_stops`, from a list already sorted by stops."""
    stops = [choice.stops for choice in choices]
    index = bisect_left(stops, wanted_stops)
    if index == 0:
        return choices[0]
    if index == len(choices):
        return choices[-1]

    below, above = choices[index - 1], choices[index]
    return below if wanted_stops - below.stops <= above.stops - wanted_stops else above


def _rank(recipe: Recipe, metered_aperture: float) -> tuple:
    """What makes one recipe better than another, most important first.

    Whether it lands at all comes first, quantised to a third of a stop, because
    inside that the camera cannot be set finely enough for the difference to
    exist. Everything after that is a price rather than an order, so that the
    four things a recipe can spend are weighed against each other instead of one
    of them always winning: a third of a stop of miss is worth fixing with a
    third of a stop of ISO, and not worth fixing with a stop of aperture.
    """
    return (
        int(abs(recipe.error_stops) / MATCHED_WITHIN_STOPS),
        _cost(recipe, metered_aperture),
    )


def _cost(recipe: Recipe, metered_aperture: float) -> float:
    """The price of a recipe in stops: what it misses by, and what it spent.

    Only the part of the miss that a camera could still close is priced, so a
    recipe never moves the photographer's aperture to buy a hundredth of a stop
    that nothing on the camera could have been set to anyway.
    """
    return (
        MISS_WEIGHT * max(0.0, abs(recipe.error_stops) - CLOSEST_SETTABLE_STOPS)
        + APERTURE_WEIGHT * abs(2 * math.log2(recipe.aperture / metered_aperture))
        + ISO_WEIGHT * max(0.0, math.log2(recipe.iso / STANDARD_ISOS[0]))
        + FILTER_WEIGHT * len(recipe.filters.filters)
    )
