"""The seven switches, read straight from the GPIO chip.

The service starts before udev has handed the chip to the gpio group, so the
thing worth pinning first is that the buttons wait for it rather than crash.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from nd_timer import fast_panel

_MAIN = Path(__file__).resolve().parent.parent / "main.py"
_spec = importlib.util.spec_from_file_location("nd_timer_main", _MAIN)
main_module = importlib.util.module_from_spec(_spec)


@pytest.fixture(scope="module", autouse=True)
def loaded():
    """main.py imports the GPIO stack lazily, so it loads off the Pi."""
    _spec.loader.exec_module(main_module)


class FakeLgpio:
    """A chip that refuses to open a set number of times, then hands out pins."""

    SET_PULL_UP = 32

    class error(Exception):
        pass

    def __init__(self, refusals: int = 0) -> None:
        self.refusals = refusals
        self.claimed: list[int] = []

    def gpiochip_open(self, chip: int) -> int:
        # What the chip does before udev has handed it to the gpio group.
        if self.refusals > 0:
            self.refusals -= 1
            raise self.error("can not open gpiochip")
        return 4

    def gpio_claim_input(self, chip: int, pin: int, flags: int) -> None:
        self.claimed.append(pin)


def test_the_buttons_wait_for_a_chip_the_boot_has_not_handed_over_yet(monkeypatch):
    # Unlike the lamp, a failure here is not survivable: it was a crash, and
    # systemd restarting the service five seconds later - every boot, now that
    # the service starts early enough to meet a chip that is not ours yet.
    monkeypatch.setattr(fast_panel, "GPIO_POLL_SECONDS", 0)
    fake = FakeLgpio(refusals=3)
    monkeypatch.setitem(sys.modules, "lgpio", fake)

    main_module.Buttons({"up": 5, "shoot": 26})

    assert fake.claimed == [5, 26]
