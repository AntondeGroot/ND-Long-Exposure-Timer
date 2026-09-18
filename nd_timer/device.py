"""The device as a whole: what each press does, and what the panel shows after it.

Shutter priority, with the filters in the loop. The photographer sets one thing -
how long the exposure should be - and everything else is worked back from it: the
filters to screw on, the ISO and aperture to set, and how close that gets. A
scenario is a shortcut to a time rather than a mode of its own, so choosing
CLOUDS puts the time in the middle of what clouds want and the recipe follows.

The pieces underneath each know one thing. The dial knows how a time steps, the
navigation knows where the five-way is pointing, the bag knows which filters are
in it, nd_timer.recipe does the solving. None of them knows that a left press
means the dial while the time is being set and the scenario otherwise. That
routing is what this is.

It holds no hardware: presses arrive as method calls and the clock arrives as an
argument, so the same state machine drives the buttons on the Pi and the browser
in scripts/simulator.py.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from nd_timer.bag import Bag
from nd_timer.camera import MeteredExposure
from nd_timer.dial import Dial
from nd_timer.exposure import filter_choices
from nd_timer.recipe import APERTURES, STANDARD_ISOS, Recipe, recipe_for
from nd_timer.subjects import SUBJECTS
from nd_timer.ui import layout
from nd_timer.ui.display import screen_for
from nd_timer.ui.navigation import Navigation
from nd_timer.ui.settings import (
    ABOUT,
    APERTURE_MAX,
    APERTURE_MIN,
    ENTRY_LABELS,
    FILTERS,
    ISO_MAX,
)

VERSION = "v0.1"

# What the dial starts on before a scenario or the photographer has said
# otherwise: a second, which is a long exposure by the time anything is on the
# lens and a sensible thing to be pointing at with no camera attached.
DEFAULT_TIME_SECONDS = 1.0


@dataclass(frozen=True)
class Shot:
    """A running exposure, timed from the clock it was started on."""

    total_seconds: float
    started_at: float

    def elapsed(self, now: float) -> float:
        return min(self.total_seconds, max(0.0, now - self.started_at))

    def remaining(self, now: float) -> float:
        return self.total_seconds - self.elapsed(now)

    def progress(self, now: float) -> float:
        if self.total_seconds <= 0:
            return 1.0
        return self.elapsed(now) / self.total_seconds

    def is_finished(self, now: float) -> bool:
        return self.remaining(now) <= 0


@dataclass(frozen=True)
class Device:
    """Everything the device knows, and every press that can change it."""

    metered: MeteredExposure | None = None
    synced_at: float | None = None
    subject_index: int = 0
    iso_max: float = 400
    aperture_min: float = APERTURES[0]
    aperture_max: float = APERTURES[-1]
    bag: Bag = Bag()
    navigation: Navigation = Navigation()
    dial: Dial = Dial(DEFAULT_TIME_SECONDS)
    shot: Shot | None = None
    battery: int = 100

    # --- what the numbers currently are -------------------------------------

    @property
    def subject(self):
        return SUBJECTS[self.subject_index]

    @property
    def exposure_seconds(self) -> float:
        """The time the shot runs for: the one the photographer asked for."""
        return self.dial.seconds

    @property
    def recipe(self) -> Recipe | None:
        """What to put on the lens for that time, once there is a scene to work from."""
        if self.metered is None:
            return None
        return recipe_for(
            wanted_seconds=self.exposure_seconds,
            metered_shutter=self.metered.shutter_seconds,
            metered_iso=self.metered.iso,
            metered_aperture=self.metered.aperture,
            choices=filter_choices(self.bag.owned),
            highest_iso=self.iso_max,
            lowest_aperture=self.aperture_min,
            highest_aperture=self.aperture_max,
        )

    # --- the presses ---------------------------------------------------------

    def pressed_up(self) -> Device:
        if self.dial.is_being_set:
            return self._with_dial(self.dial.pressed_up())
        return replace(self, navigation=self.navigation.pressed_up())

    def pressed_down(self) -> Device:
        if self.dial.is_being_set:
            return self._with_dial(self.dial.pressed_down())
        return replace(self, navigation=self.navigation.pressed_down())

    def pressed_left(self) -> Device:
        if self.dial.is_being_set:
            return self._with_dial(self.dial.pressed_left())
        return self._changed_value(-1)

    def pressed_right(self) -> Device:
        if self.dial.is_being_set:
            return self._with_dial(self.dial.pressed_right())
        return self._changed_value(1)

    def pressed_centre(self) -> Device:
        """Routed the way nd_timer.ui.navigation describes it."""
        if self.navigation.selected == layout.TIME:
            return self._with_dial(self.dial.pressed_centre())
        pointed = self.navigation.pointed_filter
        if pointed is not None:
            return replace(self, bag=self.bag.toggled(pointed))
        return replace(self, navigation=self.navigation.pressed_centre())

    def pressed_sync(self, metered: MeteredExposure, now: float) -> Device:
        """SYNC: this is the scene everything is worked back from."""
        return replace(self, metered=metered, synced_at=now)

    def pressed_shoot(self, now: float) -> Device:
        """SHOOT starts the exposure; pressing it again cancels a running one."""
        if self.shot is not None:
            return replace(self, shot=None)
        return replace(
            self,
            shot=Shot(self.exposure_seconds, now),
            dial=replace(self.dial, is_being_set=False),
        )

    def ticked(self, now: float) -> Device:
        """Back to the calculation once the shutter has closed."""
        if self.shot is not None and self.shot.is_finished(now):
            return replace(self, shot=None)
        return self

    # --- the panel -----------------------------------------------------------

    def screen(self, now: float):
        """What the panel would be showing, drawn by nd_timer.ui.display."""
        return screen_for(self, now)

    def setting_value(self, label: str) -> str:
        """What a settings entry currently says, for the list that shows it."""
        return {
            FILTERS: self.bag.summary,
            ISO_MAX: f"{self.iso_max:g}",
            APERTURE_MIN: f"f/{self.aperture_min:g}",
            APERTURE_MAX: f"f/{self.aperture_max:g}",
            ABOUT: VERSION,
        }[label]

    # --- changing a value ----------------------------------------------------

    def _changed_value(self, direction: int) -> Device:
        """Left and right, wherever the five-way happens to be.

        The filter list is changed by the centre press alone, so nothing here.
        """
        if self.navigation.on_filters_screen:
            return self
        if self.navigation.on_settings_screen:
            return self._changed_setting(direction)
        if self.navigation.selected == layout.MODE:
            return self._changed_scenario(direction)
        return self

    def _changed_scenario(self, direction: int) -> Device:
        """A scenario is a time: choosing one puts the dial in the middle of it.

        Geometrically in the middle, because exposure is a doubling scale - so
        CLOUDS, which wants two to six minutes, starts at 3m 30s rather than at
        four minutes. From there the dial is the photographer's again.
        """
        moved = replace(self, subject_index=_stepped(self.subject_index, direction, SUBJECTS))
        wanted = moved.subject.sweet_spot
        if wanted is None:
            return moved
        return moved._with_dial(self.dial.suggested(wanted))

    def _changed_setting(self, direction: int) -> Device:
        """The settings left and right change; the rest are opened by the centre."""
        entry = self.navigation.settings_entry
        if entry >= len(ENTRY_LABELS):
            return self

        changed = {
            ISO_MAX: self._changed_iso_ceiling,
            APERTURE_MIN: self._changed_widest_aperture,
            APERTURE_MAX: self._changed_narrowest_aperture,
        }.get(ENTRY_LABELS[entry])
        return changed(direction) if changed else self

    def _changed_iso_ceiling(self, direction: int) -> Device:
        index = _stepped(_nearest(STANDARD_ISOS, self.iso_max), direction, STANDARD_ISOS)
        return replace(self, iso_max=STANDARD_ISOS[index])

    def _changed_widest_aperture(self, direction: int) -> Device:
        """How far the lens opens. It stops where the other end is, rather than
        crossing it and leaving the device with no aperture it may use."""
        index = _stepped(_nearest(APERTURES, self.aperture_min), direction, APERTURES)
        return replace(self, aperture_min=min(APERTURES[index], self.aperture_max))

    def _changed_narrowest_aperture(self, direction: int) -> Device:
        """How far the lens stops down - f/22 on most, and diffraction past it."""
        index = _stepped(_nearest(APERTURES, self.aperture_max), direction, APERTURES)
        return replace(self, aperture_max=max(APERTURES[index], self.aperture_min))

    def _with_dial(self, dial: Dial) -> Device:
        return replace(self, dial=dial)


def _stepped(index: int, direction: int, values) -> int:
    """One step along a list of values, which has ends rather than wrapping.

    The selection wraps because it is a loop of places; a value does not, because
    walking off the end of the scenarios and arriving back at WAVES is never what
    the thumb meant.
    """
    return max(0, min(index + direction, len(values) - 1))


def _nearest(values: tuple, wanted: float) -> int:
    return min(range(len(values)), key=lambda i: abs(values[i] - wanted))
