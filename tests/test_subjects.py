"""Tests for what each scenario wants from an exposure."""

from nd_timer.subjects import Subject

RIVER = Subject("RIVER", 2.0, 8.0)


def test_the_arrow_points_back_into_the_range_and_not_at_its_ends():
    # Both ends belong to the range: 2s and 8s suit a river, so no arrow. Just past
    # either end the arrow points back in - longer when too short, shorter when too long.
    assert RIVER.direction_from(2.0) == 0
    assert RIVER.direction_from(8.0) == 0
    assert RIVER.direction_from(1.9) == 1
    assert RIVER.direction_from(8.1) == -1


def test_a_scenario_without_a_range_never_points():
    # NO FILTERS has no time it wants, so there is nothing to point back into - not
    # for a snapshot and not for an hour.
    no_filters = Subject("NO FILTERS", None, None, uses_filters=False)
    assert no_filters.direction_from(1 / 1000) == 0
    assert no_filters.direction_from(3600.0) == 0


def test_the_range_is_written_in_the_unit_both_ends_share():
    # Below a second a bound is a fraction, the way a camera writes a shutter speed;
    # from one second up it is a plain number. Ranges that start at a minute are
    # written in minutes, so nobody has to divide 120-360s in their head.
    assert Subject("WAVES", 1 / 15, 0.5).target_label == "1/15-1/2s"
    assert Subject("SPRAY", 1.0, 1.5).target_label == "1-1.5s"
    assert Subject("CLOUDS", 120.0, 360.0).target_label == "2-6min"
