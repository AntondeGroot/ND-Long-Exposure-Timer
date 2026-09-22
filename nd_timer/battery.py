"""What the UPS HAT has left, read off the INA219 it carries.

The chip measures volts and amps, not charge. There is no gauge on this board
modelling the cell, so the percentage is inferred from the cell voltage, which
is a cruder thing than it looks: a lithium cell sits near 3.7V for most of its
life and then falls off a cliff, and it sags under load and recovers after. A
number derived from it is an estimate wearing a percent sign.

So it is treated as one. The reading is smoothed, and it is reported in steps
of five - both because the panel would otherwise redraw every time the last
digit twitched, and because a battery indicator that claims 73% is claiming
more than it knows.
"""

from __future__ import annotations

import fcntl
import os

I2C_BUS = "/dev/i2c-1"
INA219_ADDRESS = 0x43

# Linux's ioctl for "talk to this address on this bus".
I2C_SLAVE = 0x0703

BUS_VOLTAGE_REGISTER = 0x02

# A single lithium cell: full at 4.2, and by 3.0 the protection circuit is about
# to cut in. Waveshare's own examples for this board use the same two numbers.
FULL_VOLTS = 4.2
EMPTY_VOLTS = 3.0

# Reported in steps of this, so that a reading wandering by a percent does not
# cost a panel refresh. E-paper wears with every one.
STEP_PERCENT = 5

# How much of each new reading to believe. The cell's voltage moves slowly and
# the noise does not, so most of the weight stays on what was already known.
SMOOTHING = 0.25


def percent_from(volts: float) -> int:
    """Where this voltage sits between empty and full, in steps of five."""
    fraction = (volts - EMPTY_VOLTS) / (FULL_VOLTS - EMPTY_VOLTS)
    percent = max(0.0, min(1.0, fraction)) * 100
    return int(round(percent / STEP_PERCENT) * STEP_PERCENT)


class Battery:
    """The gauge, or the absence of one.

    Every method answers None rather than raising or guessing when the chip is
    not there - a device with no UPS fitted is a normal thing, and so is a bus
    that has not been enabled yet.
    """

    def __init__(self, bus: str = I2C_BUS, address: int = INA219_ADDRESS) -> None:
        self._bus = bus
        self._address = address
        self._smoothed: float | None = None

    def volts(self) -> float | None:
        """The cell voltage, or None if the chip did not answer."""
        try:
            handle = os.open(self._bus, os.O_RDWR)
        except OSError:
            return None

        try:
            fcntl.ioctl(handle, I2C_SLAVE, self._address)
            os.write(handle, bytes([BUS_VOLTAGE_REGISTER]))
            high, low = os.read(handle, 2)
        except OSError:
            return None
        finally:
            os.close(handle)

        # The reading is in the top thirteen bits, four millivolts to a count.
        return (((high << 8) | low) >> 3) * 0.004

    def percent(self) -> int | None:
        """What to draw in the corner of the status bar."""
        volts = self.volts()
        if volts is None:
            return None

        self._smoothed = volts if self._smoothed is None else (
            self._smoothed + SMOOTHING * (volts - self._smoothed)
        )
        return percent_from(self._smoothed)
