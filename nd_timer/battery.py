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
from dataclasses import dataclass
from itertools import pairwise

I2C_BUS = "/dev/i2c-1"
INA219_ADDRESS = 0x43

# Linux's ioctl for "talk to this address on this bus".
I2C_SLAVE = 0x0703

BUS_VOLTAGE_REGISTER = 0x02
SHUNT_VOLTAGE_REGISTER = 0x01

# The shunt on this board is R9 in Waveshare's schematic for the UPS HAT (C):
# a hundredth of an ohm, so one millivolt across it is a hundred milliamps. The
# sign is the direction: into the cell is charging.
#
# It said a tenth until 2026-09-29, which read every current ten times low. The
# giveaway was the cell: at the 25mA that reported, two hours on the battery
# could not have taken it from 3.94V to 3.51V; at the 250mA it really was, it
# is half the cell, which is what that drop is.
SHUNT_OHMS = 0.01

# Below this the cell is neither charging nor running anything much - a charger
# holding it at float reads a few milliamps either way, and calling that
# "charging" would leave a bolt on the screen for ever.
CHARGING_ABOVE_MILLIAMPS = 20.0

# Where a single lithium cell's charge goes as its voltage falls, as (volts,
# percent) from full to empty. Not a straight line: the cell holds 3.6-3.8V for
# most of its charge and then falls away fast. Waveshare's example for this board
# draws a straight line from 3.0 to 4.2, which called a cell at 3.5V - nearly
# spent - 40%, and the device ran out while the corner still said plenty.
#
# A typical curve rather than this cell's own: age and temperature move it, so it
# says roughly where the charge is, which is all the corner of the screen claims.
# Empty is 3.3V, not the 3.0 the protection circuit cuts at: under the Pi's load
# there is next to nothing left below it, and the boost gives up around there.
DISCHARGE_CURVE = (
    (4.20, 100),
    (4.10, 90),
    (4.00, 80),
    (3.90, 68),
    (3.80, 55),
    (3.75, 45),
    (3.70, 35),
    (3.65, 25),
    (3.60, 17),
    (3.50, 8),
    (3.40, 3),
    (3.30, 0),
)
FULL_VOLTS = DISCHARGE_CURVE[0][0]
EMPTY_VOLTS = DISCHARGE_CURVE[-1][0]

# The cell's own resistance. Current through it moves the voltage the gauge sees -
# down while the Pi runs off it, up while it charges - and the curve above is for a
# cell at rest. A typical small lithium cell's; TODO: measured on this one, from the
# voltage and current at two different loads.
INTERNAL_OHMS = 0.15

# Reported in steps of this, so that a reading wandering by a percent does not
# cost a panel refresh. E-paper wears with every one.
STEP_PERCENT = 5

# How much of each new reading to believe. The cell's voltage moves slowly and
# the noise does not, so most of the weight stays on what was already known.
SMOOTHING = 0.25


@dataclass(frozen=True)
class Charge:
    """What the status bar needs to know about the cell."""

    percent: int
    charging: bool


def resting_volts(volts: float, milliamps: float | None) -> float:
    """The voltage with the current's push or pull through the cell taken back out.

    Positive current is into the cell, so charging comes off and a load goes back
    on. With no current to go on, the voltage is all there is.
    """
    if milliamps is None:
        return volts
    return volts - milliamps / 1000 * INTERNAL_OHMS


def percent_from(volts: float) -> int:
    """Where this voltage sits on the discharge curve, in steps of five."""
    return int(round(_on_the_curve(volts) / STEP_PERCENT) * STEP_PERCENT)


def _on_the_curve(volts: float) -> float:
    """The charge at this voltage, straight-line between the curve's neighbouring points."""
    if volts >= FULL_VOLTS:
        return 100.0
    for (upper_volts, upper), (lower_volts, lower) in pairwise(DISCHARGE_CURVE):
        if volts >= lower_volts:
            return lower + (upper - lower) * (volts - lower_volts) / (upper_volts - lower_volts)
    return 0.0


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

    def _word(self, register: int) -> int | None:
        """One sixteen-bit register, or None if the chip did not answer."""
        try:
            handle = os.open(self._bus, os.O_RDWR)
        except OSError:
            return None

        try:
            fcntl.ioctl(handle, I2C_SLAVE, self._address)
            os.write(handle, bytes([register]))
            high, low = os.read(handle, 2)
        except OSError:
            return None
        finally:
            os.close(handle)

        return (high << 8) | low

    def volts(self) -> float | None:
        """The cell voltage, or None if the chip did not answer."""
        raw = self._word(BUS_VOLTAGE_REGISTER)
        if raw is None:
            return None
        # The reading is in the top thirteen bits, four millivolts to a count.
        return (raw >> 3) * 0.004

    def milliamps(self) -> float | None:
        """Current through the shunt. Positive is into the cell: charging."""
        raw = self._word(SHUNT_VOLTAGE_REGISTER)
        if raw is None:
            return None
        signed = raw - 65536 if raw > 32767 else raw
        return (signed * 0.01) / SHUNT_OHMS

    def percent(self) -> int | None:
        """What to draw in the corner of the status bar."""
        volts = self.volts()
        if volts is None:
            return None
        return self._level(volts, self.milliamps())

    def charge(self) -> Charge | None:
        """The level and whether it is going up, or None if nothing answered."""
        volts = self.volts()
        if volts is None:
            return None

        current = self.milliamps()
        charging = current is not None and current > CHARGING_ABOVE_MILLIAMPS
        return Charge(self._level(volts, current), charging=charging)

    def _level(self, volts: float, milliamps: float | None) -> int:
        """The resting voltage, smoothed, read off the curve."""
        resting = resting_volts(volts, milliamps)
        previous = self._smoothed
        self._smoothed = resting if previous is None else previous + SMOOTHING * (resting - previous)
        return percent_from(self._smoothed)
