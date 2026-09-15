"""Golden-image tests: the screens must keep looking exactly as committed.

A change to layout, fonts or wording shows up here as a failing test. When the
change was intended, rerun scripts/render-screens.py and commit the new images -
the diff in the pull request then shows what actually changed on the panel.
"""

from pathlib import Path

import pytest
from PIL import Image

from scripts_support import CASES, render  # noqa: F401

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
    assert rendered.tobytes() == golden.tobytes(), (
        f"{name} renders differently to its committed image. "
        "If that was intended, rerun scripts/render-screens.py and commit the result."
    )
