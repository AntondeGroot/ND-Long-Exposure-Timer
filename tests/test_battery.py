"""Tests for turning a cell voltage into something worth drawing."""

from nd_timer.battery import EMPTY_VOLTS, FULL_VOLTS, STEP_PERCENT, Battery, percent_from


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
