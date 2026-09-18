"""The filters in the bag: which of the common ones the photographer owns.

The ND list on the calculator is built from these, so a filter left out of the
bag never turns up as a choice or in a suggestion. It starts full, because a
device that offers nothing until it is set up is one that looks broken.
"""

from __future__ import annotations

from dataclasses import dataclass

from nd_timer.exposure import COMMON_FILTERS, NdFilter

# How a filter's row says whether it is in the bag. A dash rather than "not
# owned": the owned ones are what the eye is looking for down the column.
OWNED = "owned"
NOT_OWNED = "-"


@dataclass(frozen=True)
class Bag:
    owned: tuple[NdFilter, ...] = COMMON_FILTERS

    def owns(self, nd_filter: NdFilter) -> bool:
        return nd_filter in self.owned

    def toggled(self, nd_filter: NdFilter) -> Bag:
        """In if it was out, out if it was in.

        The result keeps the common filters' order, so the stacks built from it do
        not depend on the order the filters happened to be ticked in.
        """
        now_owned = set(self.owned) ^ {nd_filter}
        return Bag(tuple(f for f in COMMON_FILTERS if f in now_owned))

    def ownership_label(self, nd_filter: NdFilter) -> str:
        return OWNED if self.owns(nd_filter) else NOT_OWNED

    @property
    def summary(self) -> str:
        """What the settings list says about the bag: "9 owned"."""
        return f"{len(self.owned)} {OWNED}"
