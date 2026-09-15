"""Turning a drawn frame into the bytes the panel wants.

The panel's buffer is 122 x 250, which is exactly how the screens are drawn, so
normally nothing is rotated. Rotation stays available because it depends on which
way up the HAT sits in the enclosure, and that cannot be known from here.

Packing is exactly what PIL already does for a mode-"1" image: rows of pixels,
eight to a byte, most significant bit leftmost. That means a frame can be packed
on a development machine and pushed at boot without importing Pillow at all -
which is the whole point, because importing Pillow on an armv6 Pi costs seconds
that the user spends staring at a blank panel.
"""

from __future__ import annotations

from PIL import Image

from nd_timer.ui.layout import PANEL_HEIGHT, PANEL_WIDTH

CLOCKWISE = 270
ANTICLOCKWISE = 90


def to_panel_image(frame: Image.Image, rotation: int = 0) -> Image.Image:
    """The frame as the panel will hold it: landscape, one bit deep."""
    rotated = frame.rotate(rotation, expand=True) if rotation else frame
    if rotated.size != (PANEL_WIDTH, PANEL_HEIGHT):
        raise ValueError(
            f"rotated frame is {rotated.size}, panel wants {(PANEL_WIDTH, PANEL_HEIGHT)}"
        )
    return rotated


def to_panel_bytes(frame: Image.Image, rotation: int = 0) -> bytes:
    """The packed buffer, ready to push down SPI with no Pillow at the other end."""
    return to_panel_image(frame, rotation).tobytes()
