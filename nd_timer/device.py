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
from nd_timer.exposure import FilterChoice, filter_choices
from nd_timer.recipe import APERTURES, STANDARD_ISOS, Recipe, recipe_for, recipe_of
from nd_timer.subjects import SUBJECTS
from nd_timer.ui import layout
from nd_timer.ui.display import screen_for
from nd_timer.ui.navigation import Navigation
from nd_timer.ui.settings import (
    ABOUT,
    APERTURE_MAX,
    APERTURE_MIN,
    DELAY,
    ENTRY_LABELS,
    FILTERS,
    ISO_MAX,
)

VERSION = "v0.1"

# What SHOOT waits for before opening the shutter, and what it may be set to.
# Eight seconds is long enough for a tripod to stop ringing after a finger comes
# off it, and short enough that it is not a thing you work around.
DELAYS = (0.0, 2.0, 5.0, 8.0, 10.0, 15.0, 20.0, 30.0)
DEFAULT_DELAY_SECONDS = 8.0

# Where MANUAL starts from when there is no recipe to take over: a landscape
# aperture and the bottom of the ISO ladder, which is where a tripod works.
UNMETERED_APERTURE = 11.0

# What the dial starts on before a scenario or the photographer has said
# otherwise: a second, which is a long exposure by the time anything is on the
# lens and a sensible thing to be pointing at with no camera attached.
DEFAULT_TIME_SECONDS = 1.0


@dataclass(frozen=True)
class ByHand:
    """The settings the photographer took over, and the glass they are for.

    The filters are in here because MANUAL does not re-choose them: whatever is
    screwed on stays screwed on, and the ISO and the aperture are what move
    around it. Holding all three together is what makes that true - there is no
    solving to do while this exists.
    """

    filters: FilterChoice
    iso: float
    aperture: float


@dataclass(frozen=True)
class Shot:
    """A shot from the moment SHOOT was pressed: the wait, then the exposure.

    The wait is why the two are one object. A shot is not the shutter being
    open, it is the whole thing the button started, and cancelling during the
    wait has to cancel the same thing that cancelling mid-exposure does.
    """

    total_seconds: float
    started_at: float
    delay_seconds: float = 0.0

    @property
    def opens_at(self) -> float:
        """When the shutter opens, which is not when the button was pressed."""
        return self.started_at + self.delay_seconds

    def is_delaying(self, now: float) -> bool:
        """Whether the shot has started but the shutter has not opened yet."""
        return now < self.opens_at

    def elapsed(self, now: float) -> float:
        """How long the shutter has been open, which is nothing until it is."""
        return min(self.total_seconds, max(0.0, now - self.opens_at))

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
    delay_seconds: float = DEFAULT_DELAY_SECONDS
    aperture_min: float = APERTURES[0]
    aperture_max: float = APERTURES[-1]
    bag: Bag = Bag()
    by_hand: ByHand | None = None
    navigation: Navigation = Navigation()
    dial: Dial = Dial(DEFAULT_TIME_SECONDS)
    shot: Shot | None = None
    fault: str | None = None
    # None until something answers on the I2C bus: claiming a full battery
    # because nothing has been read yet is the same lie as drawing an empty one.
    battery: int | None = None

    # --- what the numbers currently are -------------------------------------

    @property
    def subject(self):
        return SUBJECTS[self.subject_index]

    @property
    def is_auto(self) -> bool:
        """Whether the device is still choosing the settings, or the eye is."""
        return self.by_hand is None

    @property
    def selections(self) -> tuple:
        """The stops the five-way walks, which is not the same list on MANUAL."""
        return layout.selections(self.is_auto)

    @property
    def exposure_seconds(self) -> float:
        """The time the shot runs for: the one the photographer asked for."""
        return self.dial.seconds

    @property
    def recipe(self) -> Recipe | None:
        """What to put on the lens for that time, once there is a scene to work from.

        On MANUAL there is nothing to choose: the settings are the photographer's
        and this is what they come to, which is how the miss stays honest while
        they move.
        """
        if self.metered is None:
            return None
        if self.by_hand is not None:
            return recipe_of(
                wanted_seconds=self.exposure_seconds,
                metered_shutter=self.metered.shutter_seconds,
                metered_iso=self.metered.iso,
                metered_aperture=self.metered.aperture,
                filters=self.by_hand.filters,
                iso=self.by_hand.iso,
                aperture=self.by_hand.aperture,
            )
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
        return replace(self, navigation=self.navigation.pressed_up(self.selections))

    def pressed_down(self) -> Device:
        if self.dial.is_being_set:
            return self._with_dial(self.dial.pressed_down())
        return replace(self, navigation=self.navigation.pressed_down(self.selections))

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
        if self.navigation.selected == layout.AUTO:
            return self._toggled_auto()
        pointed = self.navigation.pointed_filter
        if pointed is not None:
            return replace(self, bag=self.bag.toggled(pointed))
        return replace(self, navigation=self.navigation.pressed_centre())

    def pressed_sync(self, metered: MeteredExposure, now: float) -> Device:
        """SYNC: this is the scene everything is worked back from."""
        return replace(self, metered=metered, synced_at=now, fault=None)

    def pressed_shoot(self, now: float) -> Device:
        """SHOOT starts the shot; pressing it again cancels a running one.

        The shutter does not open on the press. A finger on a button is the
        worst vibration a tripod sees all evening, and a long exposure records
        every bit of it, so the device waits for the thing to go still first.
        """
        if self.shot is not None:
            return replace(self, shot=None)
        return replace(
            self,
            shot=Shot(self.exposure_seconds, now, self.delay_seconds),
            dial=replace(self.dial, is_being_set=False),
            fault=None,
        )

    def faulted(self, message: str) -> Device:
        """The camera did not do what it was asked, so nothing is exposing.

        The shot goes with it. A countdown running against a shutter that never
        opened is the most misleading thing this device could show: it is the
        one screen a photographer walks away from.
        """
        return replace(self, fault=message, shot=None)

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
            DELAY: _delay_label(self.delay_seconds),
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

        changed = {
            layout.AUTO: lambda _: self._toggled_auto(),
            layout.ISO: self._changed_iso,
            layout.APERTURE: self._changed_aperture,
            layout.MODE: self._changed_scenario,
        }.get(self.navigation.selected)
        return changed(direction) if changed else self

    def _toggled_auto(self) -> Device:
        """MANUAL takes the settings over; AUTO hands them back.

        Taking over starts from whatever the device had chosen, so nothing jumps
        under the press: the first thing MANUAL shows is the recipe AUTO was
        showing, and from there the ISO and the aperture are yours.
        """
        if not self.is_auto:
            return replace(self, by_hand=None)
        return replace(self, by_hand=self._taken_over())

    def _taken_over(self) -> ByHand:
        recipe = self.recipe
        if recipe is None:
            return ByHand(FilterChoice((), 0.0), STANDARD_ISOS[0], UNMETERED_APERTURE)
        return ByHand(recipe.filters, recipe.iso, recipe.aperture)

    def _changed_iso(self, direction: int) -> Device:
        """The ISO by hand, still inside the ceiling the photographer set."""
        usable = [iso for iso in STANDARD_ISOS if iso <= self.iso_max] or [STANDARD_ISOS[0]]
        return self._by_hand(iso=_walked(usable, self.by_hand.iso, direction))

    def _changed_aperture(self, direction: int) -> Device:
        """The aperture by hand, still inside the lens it was told about."""
        usable = [f for f in APERTURES if self.aperture_min <= f <= self.aperture_max]
        return self._by_hand(aperture=_walked(usable or [self.by_hand.aperture], self.by_hand.aperture, direction))

    def _by_hand(self, **settings) -> Device:
        if self.by_hand is None:
            return self
        return replace(self, by_hand=replace(self.by_hand, **settings))

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
            DELAY: self._changed_delay,
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

    def _changed_delay(self, direction: int) -> Device:
        """How long the tripod is given to go still before the shutter opens."""
        index = _stepped(_nearest(DELAYS, self.delay_seconds), direction, DELAYS)
        return replace(self, delay_seconds=DELAYS[index])

    def _with_dial(self, dial: Dial) -> Device:
        return replace(self, dial=dial)


def _stepped(index: int, direction: int, values) -> int:
    """One step along a list of values, which has ends rather than wrapping.

    The selection wraps because it is a loop of places; a value does not, because
    walking off the end of the scenarios and arriving back at WAVES is never what
    the thumb meant.
    """
    return max(0, min(index + direction, len(values) - 1))


def _delay_label(seconds: float) -> str:
    """What the settings row says: a delay of nothing is off rather than "0s"."""
    return f"{seconds:g}s" if seconds else "off"


def _nearest(values, wanted: float) -> int:
    return min(range(len(values)), key=lambda i: abs(values[i] - wanted))


def _walked(ladder, from_value: float, direction: int) -> float:
    """One step along a ladder from wherever the current value sits on it."""
    return ladder[_stepped(_nearest(ladder, from_value), direction, ladder)]
