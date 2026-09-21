"""Where the five-way is pointing, and which screen that puts on the panel.

Up and down walk one list: the time, then the toggle, then the rows that can be
changed, then settings at the bottom - the order the eye reads the screen in.
The list wraps, which is what makes settings one press *up* from the time rather
than four down.

Which list it is depends on who is choosing the settings, so it is passed in
rather than known here: on AUTO the ISO and the aperture are answers and the
five-way walks past them, on MANUAL it stops on them.

Settings and the filter list inside it are lists of the same kind, each ending in
BACK. They wrap too, so BACK is one press up from the top of either.

The centre press is the one whose meaning depends on where you are. On settings
it opens the screen, on FILTERS it opens the filter list, and on BACK it goes back
one level. Two presses belong to something else, and the app hands them over
rather than this deciding for them:

    navigation.selected == layout.TIME     ->  dial.pressed_centre()
    navigation.pointed_filter is not None  ->  bag.toggled(navigation.pointed_filter)
    otherwise                              ->  navigation.pressed_centre()

Anywhere else there is nothing behind the press, so nothing happens.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from nd_timer.exposure import COMMON_FILTERS, NdFilter
from nd_timer.ui import layout
from nd_timer.ui.settings import ENTRY_LABELS, FILTERS

UP = -1
DOWN = 1


@dataclass(frozen=True)
class Navigation:
    """The selection, and which of the settings screens is over the top of it."""

    selected: str = layout.TIME
    settings_entry: int = 0
    on_settings_screen: bool = False
    filter_entry: int = 0
    on_filters_screen: bool = False

    @property
    def is_on_settings(self) -> bool:
        return self.selected == layout.SETTINGS

    @property
    def pointed_filter(self) -> NdFilter | None:
        """The filter whose row the five-way is on, if it is on one."""
        if not self.on_filters_screen or _is_back(self.filter_entry, COMMON_FILTERS):
            return None
        return COMMON_FILTERS[self.filter_entry]

    def pressed_up(self, selections: tuple = layout.AUTO_SELECTIONS) -> Navigation:
        return self._stepped(UP, selections)

    def pressed_down(self, selections: tuple = layout.AUTO_SELECTIONS) -> Navigation:
        return self._stepped(DOWN, selections)

    def pressed_centre(self) -> Navigation:
        """Open what the selection is on, or go back the way you came in."""
        if self.on_filters_screen:
            return self._pressed_centre_in_filters()
        if self.on_settings_screen:
            return self._pressed_centre_in_settings()
        if self.is_on_settings:
            return replace(self, on_settings_screen=True, settings_entry=0)
        return self

    def _pressed_centre_in_filters(self) -> Navigation:
        if _is_back(self.filter_entry, COMMON_FILTERS):
            return replace(self, on_filters_screen=False)
        return self

    def _pressed_centre_in_settings(self) -> Navigation:
        if _is_back(self.settings_entry, ENTRY_LABELS):
            return replace(self, on_settings_screen=False)
        if ENTRY_LABELS[self.settings_entry] == FILTERS:
            return replace(self, on_filters_screen=True, filter_entry=0)
        return self

    def _stepped(self, direction: int, selections: tuple) -> Navigation:
        if self.on_filters_screen:
            return replace(self, filter_entry=_stepped_through(self.filter_entry, direction, COMMON_FILTERS))
        if self.on_settings_screen:
            return replace(self, settings_entry=_stepped_through(self.settings_entry, direction, ENTRY_LABELS))
        return replace(self, selected=_next_selection(self.selected, direction, selections))


def _next_selection(selected: str, direction: int, selections: tuple) -> str:
    index = selections.index(selected) + direction
    return selections[_wrapped(index, len(selections))]


def _stepped_through(index: int, direction: int, entries: tuple) -> int:
    """One step along a settings list, whose stops are its entries then BACK."""
    return _wrapped(index + direction, len(entries) + 1)


def _is_back(index: int, entries: tuple) -> bool:
    return index == len(entries)


def _wrapped(index: int, count: int) -> int:
    return index % count
