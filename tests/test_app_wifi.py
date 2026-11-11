"""How the application carries out a Wi-Fi switch the device asked for.

The switch reboots the Pi, so nothing after it runs: whatever the panel should say
has to be on it before the switch is asked for, not after.
"""

from __future__ import annotations

import importlib.util
from dataclasses import replace
from pathlib import Path

import pytest

from nd_timer.device import Device
from nd_timer.ui.screens import RESTARTING

_MAIN = Path(__file__).resolve().parent.parent / "main.py"
_spec = importlib.util.spec_from_file_location("nd_timer_main", _MAIN)
main_module = importlib.util.module_from_spec(_spec)


@pytest.fixture(scope="module", autouse=True)
def loaded():
    """main.py imports the panel driver lazily, so it loads off the Pi."""
    _spec.loader.exec_module(main_module)


class Recorder:
    """Stands in for the panel and the Wi-Fi switch, and notes what each was asked, in order."""

    def __init__(self) -> None:
        self.events: list[tuple] = []

    def show(self, screen) -> None:
        self.events.append(("show", screen))

    def switch(self, on: bool) -> None:
        self.events.append(("switch", on))


def test_a_wifi_request_puts_restarting_on_the_panel_before_switching():
    recorder = Recorder()
    asked = replace(Device(), wifi_to_apply=False)

    main_module.carried_out_wifi(asked, panel=recorder, wifi=recorder)

    assert recorder.events == [("show", RESTARTING), ("switch", False)]
