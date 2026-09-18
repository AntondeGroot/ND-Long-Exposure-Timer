"""Tests for what a press does: the time is the input, the recipe is the answer."""

from nd_timer.bag import Bag
from nd_timer.camera import MeteredExposure
from nd_timer.device import Device
from nd_timer.exposure import COMMON_FILTERS
from nd_timer.subjects import SUBJECTS
from nd_timer.ui import layout
from nd_timer.ui.settings import DELAY, ENTRY_LABELS

DUSK = MeteredExposure(iso=100, aperture=11.0, shutter_seconds=1 / 60)
TYPICAL_BAG = Bag(tuple(f for f in COMMON_FILTERS if f.name in ("ND8", "ND64", "ND1000")))


def synced(**fields) -> Device:
    return Device(bag=TYPICAL_BAG, **fields).pressed_sync(DUSK, now=0)


def wanting(seconds: float, **fields) -> Device:
    """A synced device with the dial on a time, the way a scenario would set it."""
    device = synced(**fields)
    return Device(**{**device.__dict__, "dial": device.dial.suggested(seconds)})


def on_setting(device: Device, label: str) -> Device:
    """The five-way inside the settings list, on the entry with that label.

    Settings is one press up from the time, because the selection wraps.
    """
    opened = device.pressed_up().pressed_centre()
    for _ in range(ENTRY_LABELS.index(label)):
        opened = opened.pressed_down()
    return opened


def on_the_scenario(device: Device) -> Device:
    """The five-way one press down from where it starts, which is MODE."""
    moved = device.pressed_down()
    assert moved.navigation.selected == layout.MODE
    return moved


def test_choosing_a_scenario_sets_the_time_it_wants():
    # A scenario is a shortcut to a time rather than a mode of its own: WAVES
    # wants 1/15 to 1/2, and the dial lands geometrically in the middle of that.
    waves = on_the_scenario(synced())

    waterfall = waves.pressed_right()

    assert waterfall.subject.name == "WATERFALL"
    assert waterfall.exposure_seconds == waterfall.subject.sweet_spot


def test_the_recipe_is_worked_back_from_the_time_on_screen():
    # The panel names filters the photographer never chose: they are what the
    # time asks for, given the scene that was synced. A second from a metered
    # 1/60 is six stops, which is ND64.
    device = synced()

    assert device.exposure_seconds == 1.0
    assert device.recipe.filters.short_label == "64"

    # A couple of rungs up the dial is absorbed by the camera: two thirds of a
    # stop is not worth unscrewing a filter for.
    nudged = device.pressed_centre().pressed_right().pressed_right()

    assert nudged.exposure_seconds > device.exposure_seconds
    assert nudged.recipe.filters == device.recipe.filters
    assert (nudged.recipe.aperture, nudged.recipe.iso) != (device.recipe.aperture, device.recipe.iso)

    # Fifteen seconds is four stops past a second, which no camera can absorb.
    longer = device.pressed_centre()
    for _ in range(12):
        longer = longer.pressed_right()

    assert longer.recipe.filters.stops > device.recipe.filters.stops


def test_the_metered_shutter_is_never_restated_at_the_iso_the_recipe_chose():
    # The reading is the measurement everything else is worked out from, so it
    # stays what SYNC saw however far the ISO and the aperture have been moved
    # to reach the time. A row that quietly followed the solver would be showing
    # arithmetic rather than the scene.
    device = synced()

    dialled = device.pressed_centre()
    for _ in range(12):
        dialled = dialled.pressed_right()

    assert dialled.recipe.iso != device.recipe.iso or dialled.recipe.filters != device.recipe.filters
    assert dialled.screen(now=1).base_shutter == "1/60 s"
    assert device.screen(now=1).base_shutter == "1/60 s"


def test_the_iso_on_screen_is_the_one_that_reaches_the_time():
    # ISO is a lever on the time rather than a change to the reading: pushed up,
    # it is what makes a shorter exposure correct without touching the metered
    # shutter underneath it.
    device = synced()

    shorter = device.pressed_centre()
    for _ in range(6):
        shorter = shorter.pressed_left()

    assert shorter.exposure_seconds < device.exposure_seconds
    assert shorter.recipe.achieved_seconds < device.recipe.achieved_seconds
    assert shorter.screen(now=1).base_shutter == device.screen(now=1).base_shutter


def test_there_is_no_recipe_until_the_camera_has_been_read():
    # Nothing can be worked back from a scene the device has not seen, and a
    # confident wrong recipe is worse than none.
    assert Device().recipe is None
    assert Device().pressed_sync(DUSK, now=0).recipe is not None


def test_a_time_dialled_off_the_scenario_is_marked_as_the_photographers():
    # The rows underneath always agree with the time, so SET is not about them:
    # it says this time is yours rather than the one the scenario asked for.
    device = synced()

    dialled = device.pressed_centre().pressed_right()
    assert dialled.screen(now=1).time_is_set

    back_to_a_scenario = on_the_scenario(dialled.pressed_centre()).pressed_right()
    assert not back_to_a_scenario.screen(now=1).time_is_set


def test_the_lens_ends_bound_which_apertures_the_recipe_may_ask_for():
    # A lens that stops at f/8 is not asked for f/16, however well it would land.
    # The device works inside the kit it was told about, and says how far off it
    # ends up rather than naming an aperture the photographer does not have.
    walking = on_the_scenario(synced(aperture_min=4.0, aperture_max=8.0))

    for _ in range(len(SUBJECTS)):
        assert 4.0 <= walking.recipe.aperture <= 8.0
        walking = walking.pressed_right()


def test_narrowing_the_lens_can_cost_the_recipe_its_exactness():
    # The ends are the photographer's own limits, so they bind the search rather
    # than being traded against how well a recipe fits.
    # Three and a half minutes from a metered 1/60 sits between two stacks, and
    # ISO only ever shortens, so reaching it exactly means stopping down.
    whole_lens = wanting(208)
    one_stop_of_lens = wanting(208, aperture_min=11.0, aperture_max=11.0)

    assert whole_lens.recipe.aperture != 11.0
    assert one_stop_of_lens.recipe.aperture == 11.0
    assert abs(one_stop_of_lens.recipe.error_stops) > abs(whole_lens.recipe.error_stops)


def test_the_filters_in_the_bag_change_the_recipe_rather_than_the_time():
    # Taking a filter out of the bag cannot change what the photographer asked
    # for; it changes what the device can offer, and how close it gets.
    device = synced()
    wanted = device.exposure_seconds

    without_the_one_it_chose = Device(
        **{**device.__dict__, "bag": device.bag.toggled(device.recipe.filters.filters[0])}
    )

    assert without_the_one_it_chose.exposure_seconds == wanted
    assert without_the_one_it_chose.recipe.filters != device.recipe.filters


def test_shoot_waits_for_the_tripod_before_it_opens_the_shutter():
    # A finger coming off a button is the worst vibration a tripod sees all
    # evening, and a long exposure records every bit of it - so the press starts
    # a delay, and the exposure is counted from the shutter rather than from the
    # button. The default second of exposure therefore ends at 8 + 1.
    device = synced().pressed_shoot(now=10)

    assert device.screen(now=10).delay == "8s"
    assert device.screen(now=18.5).total == "0:01"
    assert device.ticked(now=18.5).shot is not None
    assert device.ticked(now=20).shot is None


def test_a_delay_of_nothing_opens_the_shutter_on_the_press():
    # For a remote release, or for a shot that will not wait.
    immediate = synced(delay_seconds=0.0).pressed_shoot(now=10)

    assert immediate.screen(now=10).total == "0:01"
    assert immediate.ticked(now=11.5).shot is None


def test_nothing_on_the_delay_screen_moves_while_the_delay_runs():
    # The panel takes about a second to redraw and wears a little every time, so
    # the delay is drawn once and left: a number ticking through the seconds the
    # delay exists to keep still would be both a distraction and out of date.
    device = synced().pressed_shoot(now=10)

    assert device.screen(now=10) == device.screen(now=13.7) == device.screen(now=17.9)


def test_the_countdown_holds_its_frame_for_ten_seconds_at_a_time():
    # E-paper wears a little with every refresh and takes about a second to do
    # one, so a per-second countdown is a panel that never stops redrawing. The
    # number, the bar and the elapsed all come off the same stepped clock, so
    # the whole frame is identical until the step moves.
    running = wanting(300).pressed_shoot(now=0)
    opened = running.shot.opens_at

    assert running.screen(opened + 1) == running.screen(opened + 9.9)
    assert running.screen(opened + 1) != running.screen(opened + 10.1)


def test_the_countdown_never_says_less_time_is_left_than_there_is():
    # The step rounds the elapsed down, which rounds what is left up: better to
    # be told a little more is coming than to watch it sit at zero with the
    # shutter still open.
    running = wanting(300).pressed_shoot(now=0)
    opened = running.shot.opens_at

    screen = running.screen(opened + 9)

    assert screen.remaining == "5:00"
    assert screen.elapsed == "0:00"
    assert screen.progress == 0


def test_the_shot_can_be_called_off_while_it_is_still_waiting():
    # Nothing has been recorded yet, so this is the cheapest moment to change
    # your mind - and it is the same press that stops a running exposure.
    waiting = synced().pressed_shoot(now=10)

    assert waiting.pressed_shoot(now=12).shot is None


def test_the_delay_is_dialled_in_the_settings_list():
    # Eight seconds to start with: long enough for a tripod to stop ringing,
    # short enough not to be a thing you work around.
    on_delay = on_setting(synced(), DELAY)

    assert on_delay.setting_value(DELAY) == "8s"

    shortened = on_delay.pressed_left()
    assert shortened.delay_seconds == 5.0

    turned_off = shortened.pressed_left().pressed_left()
    assert turned_off.delay_seconds == 0
    assert turned_off.setting_value(DELAY) == "off"


def test_shoot_pressed_again_cancels_the_running_exposure():
    # The one press that has to work with cold hands in the dark, so it is the
    # same button rather than a combination.
    running = synced().pressed_shoot(now=10)

    assert running.pressed_shoot(now=11).shot is None
