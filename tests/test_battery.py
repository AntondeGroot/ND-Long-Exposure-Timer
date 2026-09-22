"""Tests for turning a cell voltage into something worth drawing."""

from nd_timer.battery import (
    CHARGING_ABOVE_MILLIAMPS,
    EMPTY_VOLTS,
    FULL_VOLTS,
    STEP_PERCENT,
    Battery,
    percent_from,
)


def test_the_ends_of_the_cell_are_the_ends_of_the_scale():
    assert percent_from(FULL_VOLTS) == 100
    assert percent_from(EMPTY_VOLTS) == 0


def test_a_cell_outside_its_range_is_not_reported_outside_the_scale():
    # A fresh cell off the charger reads above 4.2, and a protection circuit cuts
    # in below 3.0. Neither is a reason to draw 104% or -8%.
    assert percent_from(4.6) == 100
    assert percent_from(2.4) == 0


def test_it_is_reported_in_steps_rather_than_to_the_percent():
    # Every change redraws the panel, and e-paper wears with each refresh - so a
    # reading wandering by a percent must not cost one. It is also more honest:
    # a voltage curve does not know the difference between 73% and 71%.
    for volts in (3.2, 3.5, 3.7, 3.9, 4.06):
        assert percent_from(volts) % STEP_PERCENT == 0


def test_nothing_on_the_bus_reads_as_unknown_rather_than_empty():
    # No UPS fitted, or the bus never enabled. Drawing a flat battery would send
    # someone home early; drawing nothing at all says what is actually known.
    absent = Battery(bus="/dev/i2c-does-not-exist")

    assert absent.volts() is None
    assert absent.percent() is None


def test_the_reading_is_smoothed_rather_than_followed():
    # A cell sags under load and recovers after, so consecutive readings differ
    # by more than the charge does. The first reading is taken as it stands -
    # there is nothing to average it with - and later ones move it gently.
    battery = Battery()
    battery.volts = lambda: 4.2
    assert battery.percent() == 100

    battery.volts = lambda: 3.0
    settled = battery.percent()

    assert 0 < settled < 100, "one low reading should not empty the battery"


def test_current_out_of_the_cell_reads_negative():
    # The shunt register is signed and the sign is the direction. Running off the
    # cell reads about minus thirteen milliamps on this board; if that came back
    # positive the panel would show a bolt on a battery that is going flat.
    battery = Battery()
    battery._word = lambda register: 0xFFFF - 12  # a small two's-complement negative

    assert battery.milliamps() < 0


def test_a_cell_being_charged_is_reported_as_charging():
    battery = Battery()
    battery.volts = lambda: 3.9
    battery.milliamps = lambda: 250.0

    charge = battery.charge()

    assert charge.charging
    assert charge.percent == percent_from(3.9)


def test_a_cell_merely_held_at_float_is_not_reported_as_charging():
    # A charger topping off trickles a few milliamps either way. Calling that
    # charging would leave a bolt on the screen for the rest of the day.
    battery = Battery()
    battery.volts = lambda: 4.2

    for idle in (CHARGING_ABOVE_MILLIAMPS - 1, 0.0, -5.0):
        battery.milliamps = lambda idle=idle: idle
        assert not battery.charge().charging


def test_a_battery_nothing_answers_for_is_not_charging_either():
    absent = Battery(bus="/dev/i2c-does-not-exist")

    assert absent.milliamps() is None
    assert absent.charge() is None


def test_a_readable_cell_with_an_unreadable_shunt_is_not_called_charging():
    # Half an answer is not evidence of a charger. The level still draws.
    battery = Battery()
    battery.volts = lambda: 3.9
    battery.milliamps = lambda: None

    assert battery.charge().charging is False
