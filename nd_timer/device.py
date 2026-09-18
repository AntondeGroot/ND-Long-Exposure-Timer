"""The device as a whole: what each press does, and what the panel shows after it.

The pieces underneath each know one thing. The dial knows how a time steps, the
navigation knows where the five-way is pointing, the bag knows which filters
exist, the exposure module does the arithmetic. None of them knows that a left
press means the dial while the time is being set and the ISO row otherwise.

That routing is what this is. It holds no hardware: the presses arrive as method
calls and the clock arrives as an argument, so the same state machine drives the
GPIO buttons on the Pi and the browser in scripts/simulator.py.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from nd_timer.bag import Bag
from nd_timer.camera import MeteredExposure
from nd_timer.dial import Dial
from nd_timer.exposure import exposure_through_filter, filter_choices, shutter_after_shift
from nd_timer.subjects import SUBJECTS
from nd_timer.suggest import STANDARD_ISOS
from nd_timer.ui import layout
from nd_timer.ui.display import screen_for
from nd_timer.ui.navigation import Navigation
from nd_timer.ui.settings import ENTRY_LABELS, FILTERS

VERSION = "v0.1"

# The settings entries this knows the value of. FILTERS comes from the bag, and
# ISO MAX is the only one left and right change rather than open.
ISO_MAX = "ISO MAX"
ABOUT = "ABOUT"

# Whole stops. The camera offers thirds, but aperture is chosen for depth of
# field rather than for exposure, so the extra rungs are steps past the one the
# photographer actually wants.
APERTURES = (1.4, 2.0, 2.8, 4.0, 5.6, 8.0, 11.0, 16.0, 22.0)
DEFAULT_APERTURE = 8.0

# What the dial starts on before anything has been metered, so a hand-set time
# is possible with no camera attached.
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
    iso_index: int = 0
    aperture_index: int = APERTURES.index(DEFAULT_APERTURE)
    nd_index: int = 0
    subject_index: int = 0
    iso_max: float = 400
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
    def choices(self) -> tuple:
        return filter_choices(self.bag.owned)

    @property
    def choice(self):
        return self.choices[min(self.nd_index, len(self.choices) - 1)]

    @property
    def working_iso(self) -> float:
        return STANDARD_ISOS[self.iso_index]

    @property
    def working_aperture(self) -> float:
        return APERTURES[self.aperture_index]

    @property
    def base_seconds(self) -> float | None:
        """The shutter once ISO and aperture have moved off the metered values."""
        if self.metered is None:
            return None
        return shutter_after_shift(
            metered_shutter=self.metered.shutter_seconds,
            metered_iso=self.metered.iso,
            metered_aperture=self.metered.aperture,
            working_iso=self.working_iso,
            working_aperture=self.working_aperture,
        )

    @property
    def calculated_seconds(self) -> float | None:
        base = self.base_seconds
        return None if base is None else exposure_through_filter(base, self.choice.stops)

    @property
    def exposure_seconds(self) -> float | None:
        """The time the device would shoot: the photographer's, or the sum's."""
        if self.dial.is_hand_set:
            return self.dial.seconds
        return self.calculated_seconds

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
            return self._with_bag(self.bag.toggled(pointed))
        return replace(self, navigation=self.navigation.pressed_centre())

    def pressed_sync(self, metered: MeteredExposure, now: float) -> Device:
        """SYNC: the camera's own exposure becomes what everything is figured from."""
        synced = replace(
            self,
            metered=metered,
            synced_at=now,
            iso_index=self._nearest_iso(metered.iso),
            aperture_index=_nearest(APERTURES, metered.aperture),
        )
        return synced._recalculated()

    def pressed_shoot(self, now: float) -> Device:
        """SHOOT starts the exposure; pressing it again cancels a running one."""
        if self.shot is not None:
            return replace(self, shot=None)
        seconds = self.exposure_seconds
        if seconds is None:
            return self
        return replace(self, shot=Shot(seconds, now), dial=replace(self.dial, is_being_set=False))

    def ticked(self, now: float) -> Device:
        """Back to the calculator once the shutter has closed."""
        if self.shot is not None and self.shot.is_finished(now):
            return replace(self, shot=None)
        return self

    # --- the panel -----------------------------------------------------------

    def screen(self, now: float):
        """What the panel would be showing, drawn by nd_timer.ui.display."""
        return screen_for(self, now)

    def setting_value(self, label: str) -> str:
        """What a settings entry currently says, for the list that shows it."""
        return {FILTERS: self.bag.summary, ISO_MAX: f"{self.iso_max:g}", ABOUT: VERSION}[label]

    # --- changing a value ----------------------------------------------------

    def _changed_value(self, direction: int) -> Device:
        """Left and right on a row, wherever the five-way happens to be."""
        if self.navigation.on_filters_screen:
            return self
        if self.navigation.on_settings_screen:
            return self._changed_setting(direction)
        return self._changed_row(direction)

    def _changed_row(self, direction: int) -> Device:
        """A parameter moving hands the answer back to the calculator."""
        moved = {
            "ISO": lambda: replace(self, iso_index=self._stepped_iso(direction)),
            "APER": lambda: replace(self, aperture_index=_stepped(self.aperture_index, direction, APERTURES)),
            "ND": lambda: replace(self, nd_index=_stepped(self.nd_index, direction, self.choices)),
            "MODE": lambda: replace(self, subject_index=_stepped(self.subject_index, direction, SUBJECTS)),
        }.get(self.navigation.selected)
        return moved()._recalculated() if moved else self

    def _changed_setting(self, direction: int) -> Device:
        """The only setting left and right can change; the rest are opened."""
        entry = self.navigation.settings_entry
        if entry >= len(ENTRY_LABELS) or ENTRY_LABELS[entry] != ISO_MAX:
            return self
        index = _stepped(_nearest(STANDARD_ISOS, self.iso_max), direction, STANDARD_ISOS)
        return replace(self, iso_max=STANDARD_ISOS[index], iso_index=min(self.iso_index, index))

    def _with_bag(self, bag: Bag) -> Device:
        """A filter leaving the bag takes its stacks with it, so ND is re-pinned."""
        kept = self.choice
        choices = filter_choices(bag.owned)
        index = next((i for i, choice in enumerate(choices) if choice == kept), 0)
        return replace(self, bag=bag, nd_index=index)._recalculated()

    def _with_dial(self, dial: Dial) -> Device:
        return replace(self, dial=dial)

    def _recalculated(self) -> Device:
        calculated = self.calculated_seconds
        return replace(self, dial=Dial(calculated if calculated is not None else self.dial.seconds))

    def _stepped_iso(self, direction: int) -> int:
        usable = [iso for iso in STANDARD_ISOS if iso <= self.iso_max] or [STANDARD_ISOS[0]]
        return min(_stepped(self.iso_index, direction, STANDARD_ISOS), len(usable) - 1)

    def _nearest_iso(self, iso: float) -> int:
        return min(_nearest(STANDARD_ISOS, iso), _nearest(STANDARD_ISOS, self.iso_max))


def _stepped(index: int, direction: int, values) -> int:
    """One step along a list of values, which has ends rather than wrapping.

    The selection wraps because it is a loop of places; a value does not, because
    walking off the end of the ISOs and arriving back at 100 is never what the
    thumb meant.
    """
    return max(0, min(index + direction, len(values) - 1))


def _nearest(values: tuple, wanted: float) -> int:
    return min(range(len(values)), key=lambda i: abs(values[i] - wanted))
