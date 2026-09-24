"""Tests for working back from a wanted time to the filters and the camera."""

import math

from nd_timer.exposure import NdFilter, filter_choices
from nd_timer.recipe import recipe_for

OWNED = (NdFilter("ND8", 3.0), NdFilter("ND64", 6.0), NdFilter("ND1000", 10.0))
CHOICES = filter_choices(OWNED)

# A scene metered at 1/60, f/11, ISO 100 - the light this device is for.
DUSK = {"metered_shutter": 1 / 60, "metered_iso": 100, "metered_aperture": 11}


def test_it_names_the_stack_that_exposes_for_the_time_that_was_asked_for():
    # 2m 19s is 13 stops past 1/60, which is ND8 and ND1000 together. Nothing
    # else has to move, so nothing else does.
    recipe = recipe_for(139, choices=CHOICES, **DUSK)

    assert recipe.filters.short_label == "8+1000"
    assert recipe.is_exact
    assert recipe.iso == 100
    assert recipe.aperture == 11


def test_iso_closes_a_gap_the_filters_cannot():
    # Two thirds of a second is 5.4 stops past 1/60 and the bag jumps 3 to 6, so
    # the filters alone land a third of a stop long. ISO is the trim: a third of
    # a stop of it costs the photograph nothing, and the aperture stays where it
    # was framed.
    recipe = recipe_for(0.707, choices=CHOICES, **DUSK)

    assert recipe.filters.short_label == "64"
    assert recipe.aperture == 11
    assert recipe.iso > 100
    assert recipe.is_as_close_as_settable


def test_iso_is_spent_to_land_the_time_rather_than_hoarded():
    # ISO 125 lands a third of a stop short and ISO 160 lands on it. A third of
    # a stop between those two is not a photograph anyone can tell apart, and a
    # third of a stop of exposure is, so the device spends the ISO.
    recipe = recipe_for(0.707, choices=CHOICES, **DUSK)

    assert recipe.is_as_close_as_settable
    assert recipe.iso == 160


def test_the_depth_of_field_is_not_bought_with_two_stops_of_iso():
    # A third of a stop of aperture would let the ISO stay at 100 here, and a
    # whole stop of it would cost two stops of ISO to reach the same time. A
    # long exposure wants base ISO, so the small aperture move is the cheaper
    # of the two - but only because it is small.
    recipe = recipe_for(208, choices=CHOICES, **DUSK)

    assert recipe.iso == 100
    assert 11 < recipe.aperture < 16
    assert recipe.is_as_close_as_settable


def test_the_aperture_moves_only_when_the_time_wanted_is_longer_than_iso_can_reach():
    # ISO only ever shortens the exposure - there is nothing below the metered
    # 100 - so a time that lands between two stacks on the long side has to be
    # bought by stopping down.
    recipe = recipe_for(208, choices=CHOICES, **DUSK)

    assert recipe.aperture > 11
    assert recipe.is_as_close_as_settable


def test_among_recipes_that_land_on_the_time_the_cleanest_capture_wins():
    # ND64 alone and ND8+ND64 with three stops of ISO both reach 1.1s. The
    # single filter wins: stacking glass costs vignetting and colour cast, and
    # both land on the time, so the tie-break is what costs the image least.
    recipe = recipe_for(1.07, choices=CHOICES, **DUSK)

    assert len(recipe.filters.filters) == 1
    assert recipe.is_exact


def test_iso_is_priced_by_where_it_sits_rather_than_by_how_far_it_moved():
    # Metered at 800 - a reading taken before the camera was on the tripod. Base
    # ISO is where a several-minute exposure wants to be, so coming down to it
    # is free, and the recipe does it rather than treating 800 as home.
    recipe = recipe_for(
        208, metered_shutter=1 / 60, metered_iso=800, metered_aperture=4.0, choices=CHOICES
    )

    assert recipe.iso == 100


def test_two_times_that_share_a_recipe_do_not_both_read_as_exact():
    # Nine and ten minutes are a sixth of a stop apart, which is inside what any
    # camera can be set to, so one recipe serves both and there is nothing to
    # change between them. They are not the same exposure though - the second is
    # a minute more cloud - so the row says which of the two it lands on rather
    # than calling both of them exact and hiding the difference.
    afternoon = {"metered_shutter": 1 / 250, "metered_iso": 100, "metered_aperture": 11}

    nine = recipe_for(9 * 60, choices=CHOICES, **afternoon)
    ten = recipe_for(10 * 60, choices=CHOICES, **afternoon)

    assert (nine.filters, nine.iso, nine.aperture) == (ten.filters, ten.iso, ten.aperture)
    assert nine.is_as_close_as_settable and ten.is_as_close_as_settable
    assert nine.error_label != ten.error_label
    assert nine.error_label == "exact"


def test_a_bag_that_cannot_reach_says_how_far_short_it_falls():
    # One three-stop filter, and minutes are being asked for. The recipe is
    # still the closest thing possible, and the miss is reported rather than
    # hidden: shooting it anyway is eight and a half stops overexposed.
    recipe = recipe_for(208, choices=filter_choices(OWNED[:1]), **DUSK)

    assert not recipe.is_matched
    assert recipe.error_stops > 8
    assert recipe.error_label == "+8.6st"


def test_the_iso_ceiling_is_never_crossed_however_well_it_would_fit():
    # The ceiling is the photographer's own limit on noise, so it outranks the
    # fit: a recipe past it is not offered, however exactly it would land.
    wanted = 4.0

    reaching = recipe_for(wanted, choices=CHOICES, highest_iso=400, **DUSK)
    capped = recipe_for(wanted, choices=CHOICES, highest_iso=200, **DUSK)

    assert reaching.iso == 400
    assert capped.iso <= 200


def test_the_error_is_what_shooting_the_wanted_time_would_cost():
    # Positive is brighter than metered: the time asked for is longer than the
    # recipe actually needs, so the frame is over by that many stops.
    recipe = recipe_for(208, choices=filter_choices(OWNED[:1]), **DUSK)

    assert recipe.error_stops == math.log2(208 / recipe.achieved_seconds)
