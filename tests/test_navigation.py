"""Tests for walking the five-way around the screen and in and out of settings."""

from nd_timer.exposure import COMMON_FILTERS
from nd_timer.ui import layout
from nd_timer.ui.navigation import Navigation
from nd_timer.ui.settings import ABOUT, ENTRY_LABELS


def test_settings_is_one_press_up_from_the_time():
    # The list wraps, so the bottom of the screen is right above the top of it -
    # and one more press up comes back round to the last row that can change.
    at_settings = Navigation().pressed_up()

    assert at_settings.selected == layout.SETTINGS
    assert at_settings.is_on_settings
    assert at_settings.pressed_up().selected == layout.SELECTABLE_ROWS[-1]


def test_down_walks_the_rows_in_reading_order_and_wraps_to_the_time():
    # The order the eye reads the screen in: the time, each row that can change,
    # then settings at the bottom - and one more press is back at the top.
    navigation = Navigation()
    visited = []
    for _ in range(len(layout.SELECTIONS) + 1):
        visited.append(navigation.selected)
        navigation = navigation.pressed_down()

    assert visited == [layout.TIME, *layout.SELECTABLE_ROWS, layout.SETTINGS, layout.TIME]


def test_centre_on_settings_opens_the_screen_at_its_first_entry():
    # Opening settings is the one press whose meaning comes from where you are,
    # and the screen always opens on the top of its list.
    opened = Navigation(selected=layout.SETTINGS).pressed_centre()

    assert opened.on_settings_screen
    assert opened.settings_entry == 0


def test_back_inside_settings_comes_back_to_where_you_went_in():
    # Leaving puts you back on settings, not at the time: the way out is the way
    # in, so a press of the centre would open it again. BACK is one press up,
    # because the list wraps.
    closed = Navigation(selected=layout.SETTINGS).pressed_centre().pressed_up().pressed_centre()

    assert not closed.on_settings_screen
    assert closed.selected == layout.SETTINGS


def test_up_and_down_inside_settings_walk_its_entries_and_wrap():
    # While the screen is open the five-way belongs to its list, which wraps like
    # the main one through BACK - and the selection underneath stays on settings.
    opened = Navigation(selected=layout.SETTINGS).pressed_centre()
    back = len(ENTRY_LABELS)

    assert opened.pressed_down().settings_entry == 1
    assert opened.pressed_up().settings_entry == back
    assert opened.pressed_up().pressed_down().settings_entry == 0
    assert opened.pressed_up().selected == layout.SETTINGS


def test_reopening_settings_starts_again_at_the_first_entry():
    # Where you were in the list last time is not remembered: each visit starts
    # at the top, so the same presses always reach the same entry. Leaving from
    # BACK means the list was last somewhere other than its top.
    left_from_back = Navigation(selected=layout.SETTINGS).pressed_centre().pressed_up().pressed_centre()

    assert left_from_back.pressed_centre().settings_entry == 0


def test_centre_on_the_version_does_nothing():
    # ABOUT only says which version is running: there is nothing behind it to
    # open or change, so the press leaves everything exactly where it was. It is
    # walked to rather than counted to, so the list can grow an entry.
    on_about = Navigation(selected=layout.SETTINGS).pressed_centre()
    for _ in range(ENTRY_LABELS.index(ABOUT)):
        on_about = on_about.pressed_down()
    assert ENTRY_LABELS[on_about.settings_entry] == ABOUT

    assert on_about.pressed_centre() == on_about


def test_centre_on_filters_opens_the_filter_list_at_its_first_filter():
    # FILTERS is the top of settings, so opening settings and pressing again is
    # the way in. It opens at the top every time - here after last leaving from
    # BACK - with settings still underneath to come back out to.
    on_filters = Navigation(selected=layout.SETTINGS).pressed_centre()
    left_from_back = on_filters.pressed_centre().pressed_up().pressed_centre()

    reopened = left_from_back.pressed_centre()

    assert reopened.on_filters_screen
    assert reopened.on_settings_screen
    assert reopened.filter_entry == 0
    assert reopened.pointed_filter == COMMON_FILTERS[0]


def test_the_pointed_filter_is_the_row_under_the_selection_and_none_on_back():
    # This is what the app toggles on a centre press, so it must be the row the
    # screen shows as selected - and nothing at all on BACK, where the press
    # belongs to the navigation instead.
    in_settings = Navigation(selected=layout.SETTINGS).pressed_centre()
    in_filters = in_settings.pressed_centre()

    assert in_filters.pressed_down().pressed_down().pointed_filter.name == "ND8"
    assert in_filters.pressed_up().pointed_filter is None
    assert in_settings.pointed_filter is None


def test_back_in_the_filter_list_returns_to_filters_in_settings():
    # BACK goes one level, not all the way out: you land on the entry you came
    # in by, still inside settings, so a second centre press goes straight back.
    in_filters = Navigation(selected=layout.SETTINGS).pressed_centre().pressed_centre()

    returned = in_filters.pressed_up().pressed_centre()

    assert not returned.on_filters_screen
    assert returned.on_settings_screen
    assert ENTRY_LABELS[returned.settings_entry] == "FILTERS"
