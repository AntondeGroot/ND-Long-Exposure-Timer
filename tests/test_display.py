"""Tests for what the panel shows for a given state of the device."""

from nd_timer.camera import MeteredExposure
from nd_timer.device import Device, Shot
from nd_timer.dial import Dial
from nd_timer.exposure import COMMON_FILTERS
from nd_timer.filter_bag import FilterBag
from nd_timer.subjects import SUBJECTS
from nd_timer.ui import layout
from nd_timer.ui.display import screen_for
from nd_timer.ui.settings import ENTRY_LABELS, FILTERS

DUSK = MeteredExposure(iso=100, aperture=11.0, shutter_seconds=1 / 60)
TYPICAL_FILTER_BAG = FilterBag(tuple(f for f in COMMON_FILTERS if f.name in ("ND8", "ND64", "ND1000")))


def on_the_mode_row(device: Device) -> Device:
    """The five-way walked down to the scenario row, wherever that is in the list."""
    for _ in range(len(device.selections)):
        if device.navigation.selected == layout.MODE:
            return device
        device = device.pressed_down()
    raise AssertionError("never reached the scenario row")


def chosen_from_the_list(name: str) -> Device:
    """A fresh device with a scenario picked from the MODES list, as the five-way would."""
    device = on_the_mode_row(Device()).pressed_centre()
    for _ in range(next(i for i, subject in enumerate(SUBJECTS) if subject.name == name)):
        device = device.pressed_down()
    return device.pressed_centre()


def test_the_countdown_is_worked_out_from_one_stepped_clock():
    # 83 seconds into a five-minute shot the clock reads 80, the last ten-second step,
    # and every number on the frame follows from that 80 - none from the live 83.
    device = Device(shot=Shot(total_seconds=300, started_at=0))
    screen = screen_for(device, now=83)
    assert (screen.remaining, screen.elapsed, screen.total) == ("3:40", "1:20", "5:00")
    assert screen.progress == 80 / 300


def test_the_countdown_at_its_end_is_full_and_at_zero():
    # 95 seconds is not a whole number of steps: once the shot is over the clock jumps
    # to the end rather than holding at 90 with five seconds that are not left. A
    # shot of no length is over from the start, and its bar is full rather than 0/0.
    finished = screen_for(Device(shot=Shot(total_seconds=95, started_at=0)), now=95)
    assert (finished.remaining, finished.progress) == ("0:00", 1.0)
    instant = screen_for(Device(shot=Shot(total_seconds=0, started_at=0)), now=0)
    assert (instant.remaining, instant.progress) == ("0:00", 1.0)


def test_the_main_screen_says_what_the_device_holds():
    # A minute on the dial in WAVES, which wants 1/15 to 1/2s: far too long, so the
    # arrow says shorter, and long enough that the camera needs bulb. The battery
    # and the bolt come from the device as they are.
    device = Device(battery=71, charging=True, dial=Dial(60.0))
    screen = screen_for(device, now=0)
    assert (screen.mode, screen.target, screen.direction) == ("WAVES", "1/15-1/2s", -1)
    assert (screen.final_time, screen.is_bulb) == ("1m", True)
    assert (screen.selected, screen.setting_time, screen.time_is_set) == ("time", False, False)
    assert (screen.is_auto, screen.shows_nudge_hint) == (True, True)
    assert (screen.battery, screen.charging) == (71, True)


def test_the_recipe_rows_are_dashes_until_sync_then_the_recipe():
    # Before SYNC there is no scene to work back from, and a dash says so. After it,
    # 208 seconds at dusk comes out as ISO 100, f/13 and the ND8 with the ND1000,
    # a tenth of a stop long.
    unsynced = screen_for(Device(filter_bag=TYPICAL_FILTER_BAG, dial=Dial(208.0)), now=0)
    assert (unsynced.iso, unsynced.aperture, unsynced.nd_label, unsynced.off_by) == ("--", "--", "--", "--")
    synced = Device(filter_bag=TYPICAL_FILTER_BAG, dial=Dial(208.0)).pressed_sync(DUSK, now=0)
    screen = screen_for(synced, now=0)
    assert (screen.iso, screen.aperture, screen.nd_label, screen.off_by) == ("100", "f/13", "8+1000", "+0.1st")


def test_the_sync_note_nags_only_when_filters_are_in_use():
    # With filters the recipe is worked out from a reading, so a missing one is worth
    # saying. NO FILTERS reads nothing, so there is nothing to nag about. A sync at
    # 100s, looked at two minutes later, is two minutes old - not 100 + 220 seconds.
    assert screen_for(Device(), now=0).synced_note == "NOT SYNCED"
    no_filters = chosen_from_the_list("NO FILTERS")
    assert no_filters.subject.name == "NO FILTERS"
    assert screen_for(no_filters, now=0).synced_note == ""
    synced = Device(filter_bag=TYPICAL_FILTER_BAG).pressed_sync(DUSK, now=100)
    assert screen_for(synced, now=220).synced_note == "SYNCED 2m"


def test_an_hour_old_sync_is_told_in_hours():
    # Minutes stop at 59: an hour is "1h" rather than "60m", and two and a half
    # hours is still "2h", whole hours only, like the minutes before it.
    synced = Device(filter_bag=TYPICAL_FILTER_BAG).pressed_sync(DUSK, now=0)
    assert screen_for(synced, now=3599).synced_note == "SYNCED 59m"
    assert screen_for(synced, now=3600).synced_note == "SYNCED 1h"
    assert screen_for(synced, now=9000).synced_note == "SYNCED 2h"


def test_the_delay_screen_carries_the_shot():
    # Three seconds into an eight-second delay the shutter has not opened: the panel
    # says what is coming - the scenario, the length and the wait - and stays put.
    device = Device(battery=62, charging=True, shot=Shot(total_seconds=208, started_at=0, delay_seconds=8))
    screen = screen_for(device, now=3)
    assert (screen.mode, screen.exposure, screen.delay, screen.is_bulb) == ("WAVES", "3m 28s", "8s", True)
    assert (screen.battery, screen.charging) == (62, True)


def test_each_list_screen_has_its_title_entries_and_carets():
    # Settings changes values with left and right, so its rows carry carets. FILTERS
    # and MODES are changed by the centre press alone, so theirs do not. Each lists
    # every entry with its value, marks the row the five-way is on, and keeps the
    # battery in the corner.
    device = Device(filter_bag=TYPICAL_FILTER_BAG, battery=55, charging=True)

    settings = device.pressed_up().pressed_centre()
    screen = screen_for(settings, now=0)
    assert (screen.title, screen.left_right_change_values, screen.selected) == ("SETTINGS", True, 0)
    assert [entry.label for entry in screen.entries] == list(ENTRY_LABELS)
    assert screen.entries[0].value == "3 owned"
    assert (screen.battery, screen.charging) == (55, True)

    filters = settings
    for _ in range(ENTRY_LABELS.index(FILTERS)):
        filters = filters.pressed_down()
    filters = filters.pressed_centre().pressed_down().pressed_down()
    screen = screen_for(filters, now=0)
    assert (screen.title, screen.left_right_change_values, screen.selected) == ("FILTERS", False, 2)
    assert [(entry.label, entry.value) for entry in screen.entries[1:3]] == [("ND4", "-"), ("ND8", "owned")]
    assert (screen.battery, screen.charging) == (55, True)

    modes = on_the_mode_row(device).pressed_centre().pressed_down()
    screen = screen_for(modes, now=0)
    assert (screen.title, screen.left_right_change_values, screen.selected) == ("MODES", False, 1)
    assert (screen.entries[1].label, screen.entries[1].value) == ("BEACH WAVE", "2-5s")
    assert (screen.battery, screen.charging) == (55, True)
