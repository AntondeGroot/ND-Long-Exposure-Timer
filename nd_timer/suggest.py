"""Choosing the filter and ISO that land the exposure where the subject wants it.

Filters come in coarse jumps - 3, 6, 9, 10 stops from a typical bag - so ND alone
often overshoots a target range. ISO is the fine adjustment: 100 to 400 is two
more stops, in thirds, and it is usually what turns "near the range" into "inside
it". Aperture is left alone, because it is chosen for depth of field rather than
for exposure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from nd_timer.exposure import FilterChoice, exposure_through_filter, shutter_after_shift
from nd_timer.subjects import Subject

# The ISOs a camera actually offers, in thirds. Anything outside the user's
# ceiling is never considered.
STANDARD_ISOS = (100, 125, 160, 200, 250, 320, 400, 500, 640, 800, 1000, 1250, 1600)


@dataclass(frozen=True)
class Suggestion:
    """A filter and an ISO that together land near the subject's target."""

    filters: FilterChoice
    iso: float
    exposure_seconds: float
    within_target: bool


def suggest(
    subject: Subject,
    metered_shutter: float,
    metered_iso: float,
    aperture: float,
    choices: tuple[FilterChoice, ...],
    lowest_iso: float = 100,
    highest_iso: float = 400,
) -> Suggestion | None:
    """The best filter and ISO for this subject, or None when there is no target.

    Anything inside the range already gives the look the subject asks for, so
    among those the cleanest capture wins: fewest filters, because stacking glass
    costs vignetting and colour cast, then lowest ISO. Only when nothing lands
    inside does proximity to the range decide, since then the look is what is at
    stake rather than the quality.
    """
    if not subject.has_target:
        return None

    usable_isos = [iso for iso in STANDARD_ISOS if lowest_iso <= iso <= highest_iso]
    if not usable_isos:
        usable_isos = [metered_iso]

    best: Suggestion | None = None
    best_rank = None

    for choice in choices:
        for iso in usable_isos:
            base = shutter_after_shift(
                metered_shutter=metered_shutter,
                metered_iso=metered_iso,
                metered_aperture=aperture,
                working_iso=iso,
                working_aperture=aperture,
            )
            exposure = exposure_through_filter(base, choice.stops)
            within = subject.direction_from(exposure) == 0

            distance = abs(math.log2(exposure / subject.sweet_spot))
            rank = (
                (0, len(choice.filters), iso, distance)
                if within
                else (1, distance, len(choice.filters), iso)
            )
            if best_rank is None or rank < best_rank:
                best_rank = rank
                best = Suggestion(choice, iso, exposure, within)

    return best
