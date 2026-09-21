#!/usr/bin/env python3
"""Find which GPIO each button is actually on, by pressing them.

RUNS ON THE PI, with nd-timer stopped - it needs the pins the service is holding:

    sudo systemctl stop nd-timer
    ./.venv/bin/python scripts/find-pins.py

Where the five-way is wired is not something a datasheet settles when the
buttons arrive through a connector on the e-paper board rather than the Pi's
header. So this asks the hardware: every pin that could be a button is claimed
as an input with a pull-up, and whichever one falls when you press something is
the answer. It prints the PINS block for main.py at the end.
"""

from __future__ import annotations

import sys
import time

import lgpio

# Everything not already spoken for. SPI has 7, 8, 9, 10 and 11; the e-paper
# board drives 17, 24 and 25 for reset, busy and data/command; 0 and 1 are the
# HAT ID EEPROM and are never wired to anything else; 14 and 15 are the serial
# console, which the boot config still enables.
CANDIDATES = (4, 5, 6, 12, 13, 16, 18, 19, 20, 21, 22, 23, 26, 27)

BUTTONS = ("up", "down", "left", "right", "centre", "sync", "shoot")

POLL_SECONDS = 0.02
SETTLE_SECONDS = 0.3


def claimed(chip: int) -> list[int]:
    """Every candidate we could actually take, as an input with a pull-up."""
    taken = []
    for pin in CANDIDATES:
        try:
            lgpio.gpio_claim_input(chip, pin, lgpio.SET_PULL_UP)
            taken.append(pin)
        except lgpio.error as exc:
            print(f"  skipping GPIO{pin}: {exc}")
    return taken


def resting(chip: int, pins: list[int]) -> dict[int, int]:
    """What each pin reads with nothing pressed.

    A pin already low is either wired to ground or driven by something else, so
    it is recorded and then ignored - it can never show a press.
    """
    time.sleep(SETTLE_SECONDS)
    return {pin: lgpio.gpio_read(chip, pin) for pin in pins}


def pressed_pin(chip: int, rest: dict[int, int]) -> int | None:
    """Block until one of the pins leaves its resting state, and say which."""
    while True:
        for pin, was in rest.items():
            if was == 1 and lgpio.gpio_read(chip, pin) == 0:
                return pin
        time.sleep(POLL_SECONDS)


def released(chip: int, pin: int) -> None:
    while lgpio.gpio_read(chip, pin) == 0:
        time.sleep(POLL_SECONDS)
    time.sleep(SETTLE_SECONDS)


def main() -> int:
    chip = lgpio.gpiochip_open(0)
    try:
        pins = claimed(chip)
        rest = resting(chip, pins)

        watching = [pin for pin, value in rest.items() if value == 1]
        grounded = [pin for pin, value in rest.items() if value == 0]
        print(f"watching {len(watching)} pins: {', '.join(f'GPIO{p}' for p in watching)}")
        if grounded:
            print(f"ignoring (already low): {', '.join(f'GPIO{p}' for p in grounded)}")
        print()

        found: dict[str, int] = {}
        for name in BUTTONS:
            print(f"  press {name.upper()} ... ", end="", flush=True)
            pin = pressed_pin(chip, rest)
            released(chip, pin)

            already = next((n for n, p in found.items() if p == pin), None)
            print(f"GPIO{pin}" + (f"  (same pin as {already}!)" if already else ""))
            found[name] = pin

        print("\nPaste this into main.py:\n")
        print("PINS = {")
        for name, pin in found.items():
            print(f'    "{name}": {pin},')
        print("}")
        return 0
    except KeyboardInterrupt:
        print("\nstopped")
        return 1
    finally:
        lgpio.gpiochip_close(chip)


if __name__ == "__main__":
    raise SystemExit(main())
