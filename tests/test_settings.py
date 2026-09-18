"""Tests for how the settings lists scroll when they are longer than the screen."""

from nd_timer.ui.settings import first_visible_entry


def test_the_window_keeps_the_selection_in_the_middle_and_stops_at_the_ends():
    # Twelve entries through a window of ten. In the middle the selection sits
    # five rows down; near either end the window stops rather than showing empty
    # rows, and on BACK (index 12, one past the entries) it rests at the end.
    count, visible = 12, 10

    assert first_visible_entry(0, count, visible) == 0
    assert first_visible_entry(6, count, visible) == 1
    assert first_visible_entry(8, count, visible) == 2
    assert first_visible_entry(11, count, visible) == 2
    assert first_visible_entry(count, count, visible) == 2


def test_a_list_that_fits_never_scrolls():
    # The settings list is three entries: it stays put from its first entry to
    # BACK, so the short list looks the same wherever the selection is on it.
    count, visible = 3, 10

    for selected in range(count + 1):
        assert first_visible_entry(selected, count, visible) == 0
