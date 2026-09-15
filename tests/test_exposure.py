"""Tests for the exposure arithmetic."""

import pytest

from nd_timer.exposure import exposure_through_filter, shutter_after_shift


def test_each_stop_of_filtration_doubles_the_exposure():
    quarter_second = 0.25
    ten_stops = 10.0

    # An ND1000 is ten stops, so 2^10 = 1024 times the time.
    assert exposure_through_filter(quarter_second, ten_stops) == pytest.approx(256.0)


def test_a_stop_of_extra_iso_buys_back_a_stop_of_shutter():
    # The spec's worked example: metered ISO 100, f/11, 1/60. Doubling the ISO
    # is one stop more light, so the shutter halves to hold the same exposure.
    shutter = shutter_after_shift(
        metered_shutter=1 / 60,
        metered_iso=100,
        metered_aperture=11,
        working_iso=200,
        working_aperture=11,
    )

    # Exactly half of 1/60. The spec quotes 1/125 because that is the nearest
    # speed a camera offers - snapping to the dial is the camera's job, not the
    # arithmetic's, and it only applies to shots the camera times itself.
    assert shutter == pytest.approx(1 / 120)
