"""What each subject wants from an exposure.

A verdict ("in range") tells you that you are wrong. A target tells you what to
aim for, which is the thing you can act on, and doubles as a reminder of what
each subject needs - the sort of thing that goes out of your head at dusk.

Every subject has a ceiling as well as a floor. Water is the clear case: too
little blur and it is a snapshot, too much and the waves stop reading as waves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SECONDS_PER_MINUTE = 60


@dataclass(frozen=True)
class Subject:
    """A kind of scene, and the exposures that suit it."""

    name: str
    shortest: float | None
    longest: float | None

    @property
    def has_target(self) -> bool:
        return self.shortest is not None and self.longest is not None

    @property
    def sweet_spot(self) -> float | None:
        """The middle of the range, geometrically.

        Exposure is a doubling scale, so the midpoint of 1s to 8s is 2.8s rather
        than 4.5s - halfway in stops, not halfway in seconds.
        """
        if not self.has_target:
            return None
        return math.sqrt(self.shortest * self.longest)

    def direction_from(self, seconds: float) -> int:
        """-1 if the exposure is too long, +1 if too short, 0 if it suits.

        The screen shows this as an arrow rather than a verdict: which way to
        move is useful, being told you are wrong is not.
        """
        if not self.has_target:
            return 0
        if seconds < self.shortest:
            return 1
        if seconds > self.longest:
            return -1
        return 0


SUBJECTS = (
    # Fast water, where the point is that it still reads as water: past about a
    # second the individual crests merge into fog.
    Subject("WAVES", 1 / 15, 0.5),
    # Silky but with strands still visible.
    Subject("WATERFALL", 0.25, 2.0),
    # Flattened texture, reflections kept.
    Subject("RIVER", 2.0, 8.0),
    Subject("CLOUDS", 2 * SECONDS_PER_MINUTE, 6 * SECONDS_PER_MINUTE),
    Subject("GLASSY", 1 * SECONDS_PER_MINUTE, 5 * SECONDS_PER_MINUTE),
    # Long enough that anyone walking through leaves no trace.
    Subject("NO PEOPLE", 2 * SECONDS_PER_MINUTE, 8 * SECONDS_PER_MINUTE),
    # No target: the calculator without the advice.
    Subject("MANUAL", None, None),
)
