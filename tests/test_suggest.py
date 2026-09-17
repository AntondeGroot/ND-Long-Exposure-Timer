"""Tests for choosing a filter and ISO to hit a subject's target."""

from nd_timer.exposure import NdFilter, filter_choices
from nd_timer.subjects import Subject
from nd_timer.suggest import suggest

OWNED = (NdFilter("ND8", 3.0), NdFilter("ND64", 6.0), NdFilter("ND1000", 10.0))


def test_among_options_in_range_it_takes_the_cleanest_capture():
    waterfall = Subject("WATERFALL", 0.25, 2.0)

    # Metered at 1/250. Both ND64 at ISO 100 (0.26s, one filter) and ND8+ND64 at
    # ISO 320 (0.64s, two filters) land in range, and the stack sits nearer the
    # middle of it. The single filter at base ISO should still win: anything in
    # range already looks right, so the tie-break is what costs the image least.
    choice = suggest(
        waterfall,
        metered_shutter=1 / 250,
        metered_iso=100,
        aperture=11,
        choices=filter_choices(OWNED),
    )

    assert choice.within_target
    assert choice.filters.short_label == "64"
    assert choice.iso == 100
