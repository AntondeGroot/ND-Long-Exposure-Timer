"""Golden-image tests: the screens must keep looking exactly as committed.

A change to layout, fonts or wording shows up here as a failing test. When the
change was intended, rerun scripts/render-screens.py and commit the new images -
the diff in the pull request then shows what actually changed on the panel.
"""

from pathlib import Path

import pytest
from PIL import Image, ImageChops
from scripts_support import CASES, render

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "docs" / "screens"


@pytest.mark.parametrize("name", sorted(CASES))
def test_screen_matches_its_committed_image(name):
    golden_path = GOLDEN_DIR / f"{name}.png"
    assert golden_path.exists(), f"no golden image for {name} - run scripts/render-screens.py"

    rendered = render(name, CASES[name])
    golden = Image.open(golden_path)

    assert rendered.size == golden.size
    assert rendered.mode == golden.mode == "1", "the panel is one bit deep"
    # Compare the packed bits, not getdata(): a mode-"1" image reports its pixels
    # as 0/1 in memory but 0/255 once round-tripped through a PNG, so getdata()
    # would report every identical image as different.
    # Compared as a bool rather than with `==` on the bytes themselves: pytest
    # expands a failing bytes comparison into a line-by-line dump of all 4000
    # bytes, which for twenty screens buries the one fact worth having.
    matches = rendered.tobytes() == golden.tobytes()
    assert matches, (
        f"{name} renders differently to its committed image: "
        f"{_pixels_differing(rendered, golden)} pixels differ. "
        "If that was intended, rerun scripts/render-screens.py and commit the result. "
        "If it was not, check that Pillow and its layout engine match CI - see "
        "nd_timer/ui/render.py:_font."
    )


def _pixels_differing(rendered: Image.Image, golden: Image.Image) -> int:
    """How far apart the two are, which the byte dump never actually said.

    Converted to "L" first, because mode "1" packs eight pixels to a byte and
    ImageChops then differences the packed bytes rather than the pixels - which
    counts an image with thirty changed pixels as twenty-six thousand.

    ImageChops rather than zip(): zip wants an explicit strict= to satisfy the
    linter, and strict= arrived in 3.10 while a development machine here may
    still be on 3.9. The sizes are asserted equal above in any case.
    """
    difference = ImageChops.difference(rendered.convert("L"), golden.convert("L"))
    return sum(1 for pixel in difference.getdata() if pixel)
