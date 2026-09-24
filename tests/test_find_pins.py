"""Tests for the pin finder, driven by a chip that replays scripted presses.

The script only does anything on a Pi with buttons attached, which is exactly
why it needs this: the one time it matters is the one time nobody wants to
discover it loops forever.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "find-pins.py"


class FakeChip:
    """A gpiochip whose pins are pressed in a scripted order.

    One read of the pin being pressed returns low, the next returns high - which
    is a press and its release, the shortest thing the script will accept.
    """

    def __init__(self, presses, busy=(), grounded=()):
        self.pending = list(presses)
        self.busy = set(busy)
        self.grounded = set(grounded)
        self.holding = None
        self.pressing = False
        self.reads = 0
        self.claimed = 0

    def claim(self, pin):
        if pin in self.busy:
            raise self.error(f"GPIO{pin} busy")
        self.claimed += 1

    def read(self, pin):
        if pin in self.grounded:
            return 0

        # The script reads every pin once to learn its resting state. Pressing
        # anything during that scan would have it recorded as permanently low.
        self.reads += 1
        if self.reads <= self.claimed:
            return 1

        if self.holding is None:
            if not self.pending:
                return 1
            self.holding, self.pressing = self.pending[0], True

        if pin != self.holding:
            return 1
        if self.pressing:
            self.pressing = False
            return 0

        self.pending.pop(0)
        self.holding = None
        return 1


def run_finder(chip):
    """Load the script against a fake lgpio and run it, returning its output."""
    fake = types.ModuleType("lgpio")
    fake.SET_PULL_UP = 32
    fake.error = type("error", (Exception,), {})
    fake.gpiochip_open = lambda number: 1
    fake.gpiochip_close = lambda handle: None
    fake.gpio_claim_input = lambda handle, pin, flags: chip.claim(pin)
    fake.gpio_read = lambda handle, pin: chip.read(pin)
    chip.error = fake.error

    saved = sys.modules.get("lgpio")
    sys.modules["lgpio"] = fake
    try:
        spec = importlib.util.spec_from_file_location("find_pins", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.POLL_SECONDS = 0
        module.SETTLE_SECONDS = 0
        return module, module.main()
    finally:
        sys.modules.pop("lgpio", None)
        if saved is not None:
            sys.modules["lgpio"] = saved


@pytest.fixture
def wiring():
    return {"up": 6, "down": 19, "left": 5, "right": 26, "centre": 13, "sync": 20, "shoot": 21}


def test_it_reports_the_pin_each_button_was_pressed_on(capsys, wiring):
    # The whole job: press them in the order it asks, get the block back.
    _, status = run_finder(FakeChip([wiring[name] for name in
                                          ("up", "down", "left", "right", "centre", "sync", "shoot")]))
    printed = capsys.readouterr().out

    assert status == 0
    for name, pin in wiring.items():
        assert f'"{name}": {pin},' in printed


def test_a_pin_something_else_holds_is_skipped_rather_than_fatal(capsys, wiring):
    # SPI and the e-paper own several pins, and claiming one of those raises.
    # Losing a candidate is not a reason to stop looking at the rest.
    chip = FakeChip([wiring[name] for name in
                     ("up", "down", "left", "right", "centre", "sync", "shoot")], busy=(18, 23))
    _, status = run_finder(chip)
    printed = capsys.readouterr().out

    assert status == 0
    assert "skipping GPIO18" in printed and "skipping GPIO23" in printed


def test_a_pin_already_low_is_ignored_because_it_can_never_show_a_press(capsys, wiring):
    # Wired to ground, or driven by something else: either way it reads low for
    # ever, and watching it would report it as the answer to the first question.
    chip = FakeChip([wiring[name] for name in
                     ("up", "down", "left", "right", "centre", "sync", "shoot")], grounded=(22,))
    _, status = run_finder(chip)
    printed = capsys.readouterr().out

    assert status == 0
    assert "ignoring (already low): GPIO22" in printed
    assert '"up": 22,' not in printed


def test_the_same_pin_twice_is_called_out(capsys, wiring):
    # Pressing the wrong button, or two names on one wire. Silently mapping both
    # would leave one of them doing nothing and no clue as to why.
    pins = [wiring[name] for name in ("up", "down", "left", "right", "centre", "sync", "shoot")]
    pins[1] = pins[0]
    _, status = run_finder(FakeChip(pins))
    printed = capsys.readouterr().out

    assert status == 0
    assert "same pin as up" in printed
