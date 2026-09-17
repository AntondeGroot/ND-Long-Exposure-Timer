"""Tests for setting the exposure time by hand."""

from nd_timer.dial import LONGEST_SECONDS, Dial, dialled_label, longer, nudged, shorter


def test_the_minute_region_starts_at_sixteen_seconds():
    # The ladder's top rung is 15s. One press further is where the steps become
    # whole minutes and the time starts being written as a clock.
    assert longer(15.0) == 16.0
    assert dialled_label(15.0) == "15 s"
    assert dialled_label(16.0) == "00:16"


def test_the_ladder_reaches_the_speeds_the_camera_times_itself():
    # The fast end is not long-exposure work: waves want 1/8, and a dial that
    # goes to 1/125 is one a self-timer can be built on later. Below the floor
    # a left press stays put rather than walking off the bottom of the ladder.
    assert dialled_label(1 / 8) == "1/8 s"
    assert dialled_label(shorter(1 / 8)) == "1/10 s"
    assert shorter(1 / 125) == 1 / 125


def test_seconds_are_offered_only_where_a_second_is_an_adjustment():
    # A second added to 1/8 is three stops, so the screen does not offer it as a
    # fine control - but the press still works, and still comes back, because a
    # second is often exactly how you leave the fast end.
    fast = _setting(1 / 8)
    assert not fast.shows_nudge_hint
    assert fast.pressed_up().label == "1.1 s"
    assert fast.pressed_up().pressed_down().label == "1/8 s"

    slow = _setting(2.0)
    assert slow.shows_nudge_hint
    assert slow.pressed_up().label == "3.0 s"


def test_right_rounds_up_to_the_next_whole_minute():
    # Past the ladder the steps are minutes, and they land on the minute rather
    # than adding sixty seconds to wherever the time happened to be.
    assert longer(16.0) == 60.0
    assert dialled_label(longer(137.0)) == "03:00"


def test_left_leaves_the_minute_region_through_its_bottom_rung():
    # Rounding 40s down to a whole minute would be zero, so the way out is 00:16
    # and the ladder takes over from there.
    assert shorter(137.0) == 120.0
    assert shorter(60.0) == 16.0
    assert shorter(16.0) == 15.0


def test_up_and_down_move_one_second_and_undo_each_other():
    # The seconds between the rungs are only reachable this way, so a press that
    # did not come back exactly would strand the time between them.
    dial = _setting(139.0).pressed_up().pressed_up()

    assert dial.label == "02:21"
    assert dial.pressed_down().pressed_down().label == "02:19"


def test_the_time_only_moves_once_setting_has_started():
    # Until the centre press the five-way is moving between rows and changing
    # ISO, so a left or right arriving here must not quietly change the exposure.
    calculated = Dial(137.0)

    assert calculated.pressed_right().seconds == 137.0
    assert calculated.pressed_up().seconds == 137.0
    assert not calculated.pressed_right().is_hand_set


def test_a_hand_set_time_is_marked_until_it_is_recalculated():
    # The mark is what stops the panel showing a time that contradicts the
    # working printed under it. Stopping setting keeps it; a parameter moving
    # underneath hands the answer back to the calculator.
    dial = _setting(137.0).pressed_right()

    assert dial.is_hand_set
    assert dial.pressed_centre().is_hand_set

    recalculated = dial.recalculated(17.0)
    assert not recalculated.is_hand_set
    assert recalculated.label == "17 s"


def test_the_dial_stops_at_an_hour():
    # Where the battery, the sensor and mm:ss all run out together.
    assert longer(LONGEST_SECONDS) == LONGEST_SECONDS
    assert nudged(LONGEST_SECONDS, 1) == LONGEST_SECONDS
    assert dialled_label(LONGEST_SECONDS) == "60:00"


def _setting(seconds: float) -> Dial:
    """A dial with the centre already pressed, which is when the presses count."""
    return Dial(seconds).pressed_centre()
