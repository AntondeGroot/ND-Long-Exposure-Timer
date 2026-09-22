"""The settings screens: the device's own lists, drawn the way the calculator's is.

Settings are the things that are true of the bag rather than of the shot - which
filters are in it, how far the ISO may be pushed and how wide and how far down
the lens goes when the device goes looking for a recipe. They change rarely enough to be worth a screen of their own, and the
calculator is the better for not carrying them.

The filter list is the same screen one level down, under its own title, so it is
drawn here too.

The entries arrive already written, the same way every other screen takes its
numbers: whatever owns a setting knows how to say it, and this only draws it.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import ImageDraw

from nd_timer.ui import layout, render

# What the screen lists, in the order it lists them. The navigation walks this,
# so it is the one place the list is written down.
#
# Four of them are the shape of the kit: which filters are in the bag, how far
# the ISO may be pushed, and how wide and how far down the lens goes. Between
# them they are the whole search space the device is allowed to answer from.
# The fifth is the wait between the press and the shutter.
FILTERS = "FILTERS"
ISO_MAX = "ISO MAX"
APERTURE_MIN = "APER MIN"
APERTURE_MAX = "APER MAX"
DELAY = "DELAY"
ABOUT = "ABOUT"

ENTRY_LABELS = (FILTERS, ISO_MAX, APERTURE_MIN, APERTURE_MAX, DELAY, ABOUT)


@dataclass(frozen=True)
class SettingsEntry:
    """One line of the list: what it is called, and what it currently says."""

    label: str
    value: str


@dataclass(frozen=True)
class SettingsScreen:
    """Everything a settings screen shows.

    `selected` counts one past the entries: that last stop is BACK, which is how
    the list is left now that the centre press opens or changes what it is on.

    The filter list is changed by the centre press alone, so its rows are drawn
    without the carets that promise left and right will do something.
    """

    entries: tuple[SettingsEntry, ...]
    selected: int
    battery: int | None
    title: str = "SETTINGS"
    left_right_change_values: bool = True

    @property
    def is_on_back(self) -> bool:
        return self.selected == len(self.entries)


def render_settings(screen: SettingsScreen):
    frame = render.blank_frame()
    draw = ImageDraw.Draw(frame)

    render.draw_status_bar(draw, screen.title, screen.battery)
    _draw_entries(draw, screen)
    render.draw_banner_footer(draw, "BACK", selected=screen.is_on_back)
    return frame


def first_visible_entry(selected: int, count: int, visible: int = layout.SETTINGS_VISIBLE_ROWS) -> int:
    """Where the window onto a long list starts, so the selection stays in it.

    The selection is kept in the middle of the window wherever the list allows,
    so there are always rows showing on both sides of it to say where a press
    will go. Worked out from the selection alone: the screen need not remember
    where it was scrolled to, and the same presses always show the same rows.
    On BACK, one past the entries, the window rests at the end of the list.
    """
    if count <= visible:
        return 0
    return max(0, min(selected - visible // 2, count - visible))


def _draw_entries(draw: ImageDraw.ImageDraw, screen: SettingsScreen) -> None:
    """The list, starting straight under the status bar.

    There is no answer to make room for here, so the entries begin where the
    calculator's would if it had nothing to say - and they are the same row, so
    a setting is read with the same glance as a parameter.
    """
    count = len(screen.entries)
    first = first_visible_entry(screen.selected, count)
    last = min(first + layout.SETTINGS_VISIBLE_ROWS, count)

    for row, index in enumerate(range(first, last)):
        entry = screen.entries[index]
        render.draw_value_row(
            draw, layout.settings_row_top(row), entry.label, entry.value, index == screen.selected,
            carets=screen.left_right_change_values,
        )

    if first > 0:
        _draw_scroll_hint(draw, layout.SCROLL_HINT_UP_TOP, points_up=True)
    if last < count:
        _draw_scroll_hint(draw, layout.SCROLL_HINT_DOWN_TOP, points_up=False)


def _draw_scroll_hint(draw: ImageDraw.ImageDraw, top: int, points_up: bool) -> None:
    """A small solid triangle, centred, pointing at the rows that are off screen."""
    bottom = top + layout.SCROLL_HINT_HEIGHT - 1
    tip_y, base_y = (top, bottom) if points_up else (bottom, top)
    centre = layout.CENTRE_X
    half = layout.SCROLL_HINT_HALF_WIDTH
    draw.polygon([(centre, tip_y), (centre - half, base_y), (centre + half, base_y)], fill=layout.BLACK)
