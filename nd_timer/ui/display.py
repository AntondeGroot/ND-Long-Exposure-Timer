"""What the panel shows for a given state of the device.

The screens take plain strings so that they can be drawn and compared without a
running device. The device holds numbers, because that is what the arithmetic
needs. This is the one place the two meet: every number written for the eye is
written here, and each screen is chosen by the one thing that is true of the
device at that moment.

The main screen reads as one sentence down the column: this was the scene, and
this is the ISO, the aperture and the filters that turn it into the time at the
top. Only the first row is a measurement; the rest are instructions.
"""

from __future__ import annotations

from nd_timer.exposure import (
    COMMON_FILTERS,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
    format_exposure,
    needs_bulb,
)
from nd_timer.ui.screens import CountdownScreen, MainScreen
from nd_timer.ui.settings import ENTRY_LABELS, FILTERS, SettingsEntry, SettingsScreen

NOT_SYNCED = "NOT SYNCED"
NO_VALUE = "--"


def screen_for(device, now: float):
    """The screen the panel would be holding, given the device and the clock."""
    if device.shot is not None:
        return _countdown_screen(device, now)
    if device.navigation.on_filters_screen:
        return _filters_screen(device)
    if device.navigation.on_settings_screen:
        return _settings_screen(device)
    return _main_screen(device, now)


def _main_screen(device, now: float) -> MainScreen:
    """The time the photographer asked for, and what it would take to shoot it."""
    seconds = device.exposure_seconds
    recipe = device.recipe
    return MainScreen(
        mode=device.subject.name,
        iso=_recipe_value(recipe, lambda r: f"{r.iso:g}"),
        aperture=_recipe_value(recipe, lambda r: f"f/{r.aperture:g}"),
        nd_label=_recipe_value(recipe, lambda r: r.filters.short_label),
        off_by=_recipe_value(recipe, lambda r: r.error_label),
        selected=device.navigation.selected,
        base_shutter=_metered_shutter(device),
        final_time=device.dial.label,
        setting_time=device.dial.is_being_set,
        shows_nudge_hint=device.dial.shows_nudge_hint,
        time_is_set=device.dial.is_hand_set,
        target=device.subject.target_label,
        direction=device.subject.direction_from(seconds),
        is_bulb=needs_bulb(seconds),
        synced_note=_synced_note(device, now),
        battery=device.battery,
    )


def _countdown_screen(device, now: float) -> CountdownScreen:
    shot = device.shot
    return CountdownScreen(
        mode=device.subject.name,
        remaining=_clock(shot.remaining(now)),
        elapsed=_clock(shot.elapsed(now)),
        total=_clock(shot.total_seconds),
        progress=shot.progress(now),
        is_bulb=needs_bulb(shot.total_seconds),
        battery=device.battery,
    )


def _settings_screen(device) -> SettingsScreen:
    return SettingsScreen(
        entries=tuple(SettingsEntry(label, device.setting_value(label)) for label in ENTRY_LABELS),
        selected=device.navigation.settings_entry,
        battery=device.battery,
    )


def _filters_screen(device) -> SettingsScreen:
    """The bag, one filter a line. Left and right do nothing here, so no carets."""
    return SettingsScreen(
        entries=tuple(
            SettingsEntry(f.name, device.bag.ownership_label(f)) for f in COMMON_FILTERS
        ),
        selected=device.navigation.filter_entry,
        battery=device.battery,
        title=FILTERS,
        left_right_change_values=False,
    )


def _metered_shutter(device) -> str:
    """The shutter the camera was reading when SYNC was pressed.

    Nothing the device does moves it. It is the measurement the whole recipe is
    worked out from, and a row that quietly restated it at each ISO the solver
    tried would be showing arithmetic rather than the scene.
    """
    if device.metered is None:
        return NO_VALUE
    return format_exposure(device.metered.shutter_seconds)


def _recipe_value(recipe, written) -> str:
    """A row of the recipe, or a dash while there is no scene to solve for.

    Before SYNC there is nothing to work back from, and a row of confident
    numbers would be a worse answer than saying so.
    """
    return NO_VALUE if recipe is None else written(recipe)


def _synced_note(device, now: float) -> str:
    """How long ago SYNC was pressed: a stale sync is a wrong answer."""
    if device.synced_at is None:
        return NOT_SYNCED
    return f"SYNCED {_age(now - device.synced_at)}"


def _clock(seconds: float) -> str:
    """m:ss, which is how a countdown is read at a glance."""
    minutes, remainder = divmod(int(round(seconds)), SECONDS_PER_MINUTE)
    return f"{minutes}:{remainder:02d}"


def _age(seconds: float) -> str:
    """How long ago, kept to two characters where it can be."""
    if seconds < SECONDS_PER_MINUTE:
        return f"{int(seconds)}s"
    if seconds < SECONDS_PER_HOUR:
        return f"{int(seconds // SECONDS_PER_MINUTE)}m"
    return f"{int(seconds // SECONDS_PER_HOUR)}h"
