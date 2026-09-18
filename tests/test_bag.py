"""Tests for choosing which filters are in the bag."""

from nd_timer.bag import Bag
from nd_timer.exposure import COMMON_FILTERS

FILTERS_BY_NAME = {f.name: f for f in COMMON_FILTERS}
ND2 = FILTERS_BY_NAME["ND2"]
ND8 = FILTERS_BY_NAME["ND8"]
ND64 = FILTERS_BY_NAME["ND64"]


def test_toggling_a_filter_takes_it_out_and_puts_it_back_in_order():
    # The stacks are built from the bag in its own order, so a filter ticked last
    # must still land where it belongs rather than on the end - ND2 goes in front.
    bag = Bag((ND8, ND64))

    assert bag.toggled(ND64).owned == (ND8,)
    assert bag.toggled(ND2).owned == (ND2, ND8, ND64)
    assert bag.toggled(ND64).toggled(ND64) == bag


def test_the_bag_summary_counts_what_is_owned():
    # The settings row says how many filters are in the bag, and it follows the
    # ticks - an empty bag is allowed, and says so rather than going blank.
    bag = Bag((ND8, ND64))

    assert bag.summary == "2 owned"
    assert bag.toggled(ND2).summary == "3 owned"
    assert Bag(()).summary == "0 owned"
