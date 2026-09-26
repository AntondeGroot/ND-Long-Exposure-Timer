"""The lamp in the power button, which is the only thing that can say "starting".

The power switch cuts the rail, so nothing runs at power-off to leave a message
on the panel, and the panel cannot be written until Linux is up. The firmware
lights this lamp from config.txt about a second in; all the application does is
put it out honestly, once there is a screen worth looking at.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MAIN = Path(__file__).resolve().parent.parent / "main.py"
_spec = importlib.util.spec_from_file_location("nd_timer_main", _MAIN)
main_module = importlib.util.module_from_spec(_spec)


@pytest.fixture(scope="module", autouse=True)
def loaded():
    """main.py imports the GPIO stack lazily, so it loads off the Pi."""
    _spec.loader.exec_module(main_module)


class FakeLgpio:
    def __init__(self) -> None:
        self.writes: list[tuple[int, int]] = []
        self.claimed: list[tuple[int, int]] = []
        self.closed = False

    def gpiochip_open(self, chip: int) -> int:
        return 4

    def gpio_claim_output(self, chip: int, pin: int, level: int) -> None:
        self.claimed.append((pin, level))

    def gpio_write(self, chip: int, pin: int, level: int) -> None:
        self.writes.append((pin, level))

    def gpiochip_close(self, chip: int) -> None:
        self.closed = True


def test_the_lamp_is_claimed_lit_and_put_out_exactly_once(monkeypatch):
    # Claimed high because the firmware already has it high: claiming it low
    # would blink the lamp off and on again on the way past. And ready() is
    # called on every frame the loop draws, so it has to be idempotent - the
    # lamp must not be rewritten twenty times a second for the rest of the run.
    fake = FakeLgpio()
    monkeypatch.setitem(sys.modules, "lgpio", fake)

    led = main_module.StatusLed(22)
    assert fake.claimed == [(22, 1)]

    led.ready()
    led.ready()
    led.ready()

    assert fake.writes == [(22, 0)]
