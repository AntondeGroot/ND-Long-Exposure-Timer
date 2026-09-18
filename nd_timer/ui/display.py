"""What the panel shows for a given state of the device.

The screens take plain strings so that they can be drawn and compared without a
running device. The device holds numbers, because that is what the arithmetic
needs. This is the one place the two meet: every number written for the eye is
written here, and each screen is chosen by the one thing that is true of the
device at that moment.
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
    seconds = device.exposure_seconds
    metered = device.metered is not None
    return MainScreen(
        mode=device.subject.name,
        iso=_if_metered(metered, f"{device.working_iso:g}"),
        aperture=_if_metered(metered, f"f/{device.working_aperture:g}"),
        nd_label=device.choice.short_label,
        nd_stops=device.choice.stops_label,
        selected=device.navigation.selected,
        base_shutter=_if_metered(metered, _exposure(device.base_seconds)),
        final_time=device.dial.label if seconds is not None else NO_VALUE,
        setting_time=device.dial.is_being_set,
        shows_nudge_hint=device.dial.shows_nudge_hint,
        time_is_set=device.dial.is_hand_set,
        target=device.subject.target_label,
        direction=device.subject.direction_from(seconds) if seconds else 0,
        is_bulb=seconds is not None and needs_bulb(seconds),
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


def _if_metered(metered: bool, text: str) -> str:
    """Values that mean nothing until the camera has been read say so."""
    return text if metered else NO_VALUE


def _synced_note(device, now: float) -> str:
    """How long ago SYNC was pressed: a stale sync is a wrong answer."""
    if device.synced_at is None:
        return NOT_SYNCED
    return f"SYNCED {_age(now - device.synced_at)}"


def _exposure(seconds: float | None) -> str:
    return NO_VALUE if seconds is None else format_exposure(seconds)


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
