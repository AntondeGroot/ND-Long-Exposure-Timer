"""The settings, kept across restarts: the filter bag, the ISO ceiling, the lens ends and
the delay - everything on the Settings screen.

Only those. They describe the photographer's gear and how they like to work, which does
not change between evenings; the time, the scenario and a sync reading describe tonight's scene, and
starting those afresh is right.

The file is small JSON, written whole to a temporary file and renamed over the old
one, so a power cut mid-write leaves the previous settings rather than half of a file.
Reading is forgiving in the other direction: a missing file, a corrupt one, or a value
this version does not know - a filter renamed, an ISO dropped from the ladder - falls
back to the default for that one setting, because a device that will not start over a
settings file is worse than one that forgot a setting.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from nd_timer.device import DELAYS, Device
from nd_timer.exposure import COMMON_FILTERS
from nd_timer.filter_bag import FilterBag
from nd_timer.recipe import APERTURES, STANDARD_ISOS


def settings_of(device: Device) -> dict:
    """The settings as plain JSON values."""
    return {
        "filters": [f.name for f in device.filter_bag.owned],
        "iso_max": device.iso_max,
        "aperture_min": device.aperture_min,
        "aperture_max": device.aperture_max,
        "delay_seconds": device.delay_seconds,
    }


def with_settings(device: Device, settings: dict) -> Device:
    """The device with every setting this version recognises taken from `settings`."""
    defaults = Device()
    aperture_min = _one_of(settings.get("aperture_min"), APERTURES, defaults.aperture_min)
    aperture_max = _one_of(settings.get("aperture_max"), APERTURES, defaults.aperture_max)
    if aperture_min > aperture_max:
        aperture_min, aperture_max = defaults.aperture_min, defaults.aperture_max
    return replace(
        device,
        filter_bag=_bag(settings.get("filters"), defaults.filter_bag),
        iso_max=_one_of(settings.get("iso_max"), STANDARD_ISOS, defaults.iso_max),
        aperture_min=aperture_min,
        aperture_max=aperture_max,
        delay_seconds=_one_of(settings.get("delay_seconds"), DELAYS, defaults.delay_seconds),
    )


class SettingsFile:
    """The settings on disk: restored once at start, saved whenever it changes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._saved: dict | None = None

    def restored(self, device: Device) -> Device:
        try:
            settings = json.loads(self._path.read_text())
        except (OSError, ValueError):
            return device
        if not isinstance(settings, dict):
            return device
        restored = with_settings(device, settings)
        self._saved = settings_of(restored)
        return restored

    def save_if_changed(self, device: Device) -> None:
        """Write the settings if they differ from what was last read or written.

        Called every turn of the loop, so the comparison is what keeps this from writing
        to the SD card twenty times a second. A write that fails - a read-only card, a
        full one - is reported and the device carries on: losing a setting at the next
        restart beats stopping now.
        """
        settings = settings_of(device)
        if settings == self._saved:
            return
        temporary = self._path.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(settings, indent=2))
            os.replace(temporary, self._path)
        except OSError as error:
            print(f"could not save the settings: {error}", file=sys.stderr)
        self._saved = settings


def _one_of(value, allowed, default):
    return value if value in allowed else default


def _bag(names, default: FilterBag) -> FilterBag:
    """The common filters named in `names`, in their usual order; names this version does
    not know are dropped."""
    if not isinstance(names, list):
        return default
    return FilterBag(tuple(f for f in COMMON_FILTERS if f.name in names))
