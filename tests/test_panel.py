"""The frame-to-bytes contract: what actually travels down SPI to the panel.

Worth pinning precisely rather than loosely. Every failure this module can
produce - the wrong bit order, inverted polarity, the row padding miscounted -
shows up on the glass as a shifted or mirrored screen, which looks exactly like
a wiring fault and costs an evening to tell apart from one.
"""

import pytest
from PIL import Image

from nd_timer.ui.layout import PANEL_HEIGHT, PANEL_WIDTH
from nd_timer.ui.panel import ANTICLOCKWISE, CLOCKWISE, to_panel_bytes, to_panel_image

# 122 pixels needs 16 bytes: fifteen full ones and two pixels in the sixteenth,
# leaving six bits of padding that belong to no pixel at all.
BYTES_PER_ROW = 16
PADDING_BITS = BYTES_PER_ROW * 8 - PANEL_WIDTH


def panel_sized(fill: int = 1) -> Image.Image:
    """A frame the size the panel holds. fill=1 is white, fill=0 black."""
    return Image.new("1", (PANEL_WIDTH, PANEL_HEIGHT), fill)


def test_a_frame_already_the_panel_shape_is_passed_through_untouched():
    frame = panel_sized()

    assert to_panel_image(frame) is frame, "an unrotated frame should not be copied"


def test_a_frame_of_the_wrong_shape_is_refused_rather_than_sent():
    # Sending a short buffer does not fail loudly at the panel - it draws
    # whatever the bytes happen to mean, and the screen goes to nonsense. The
    # error names both sizes because "wrong size" alone does not say which way.
    frame = Image.new("1", (PANEL_WIDTH, PANEL_HEIGHT - 1), 1)

    with pytest.raises(ValueError) as refusal:
        to_panel_image(frame)

    assert str((PANEL_WIDTH, PANEL_HEIGHT - 1)) in str(refusal.value)
    assert str((PANEL_WIDTH, PANEL_HEIGHT)) in str(refusal.value)


@pytest.mark.parametrize("rotation", [CLOCKWISE, ANTICLOCKWISE])
def test_a_landscape_frame_becomes_the_panel_shape_when_turned(rotation):
    # Which way up the HAT sits in the enclosure cannot be known from here, so
    # both quarter turns have to land on the panel's own shape.
    landscape = Image.new("1", (PANEL_HEIGHT, PANEL_WIDTH), 1)

    assert to_panel_image(landscape, rotation).size == (PANEL_WIDTH, PANEL_HEIGHT)


def test_the_buffer_is_one_row_of_whole_bytes_per_line():
    assert len(to_panel_bytes(panel_sized())) == BYTES_PER_ROW * PANEL_HEIGHT


def test_white_is_ones_and_black_is_zeros():
    # The panel reads a 1 bit as white. Inverted, every screen comes out as its
    # own negative - legible, which is what makes it easy to miss in review.
    assert set(to_panel_bytes(panel_sized(fill=0))) == {0x00}
    assert set(to_panel_bytes(panel_sized(fill=1))) == {0xFF, 0xC0}


def test_the_bits_past_the_end_of_a_row_are_not_pixels():
    # 122 is not a multiple of 8, so six bits of the last byte in each row mean
    # nothing. On an all-white frame they stay clear, which is why the row ends
    # 0xC0 and not 0xFF - the two set bits are the row's last two pixels.
    row = to_panel_bytes(panel_sized())[:BYTES_PER_ROW]

    assert row[:-1] == bytes([0xFF]) * (BYTES_PER_ROW - 1)
    assert row[-1] == 0xC0
    assert bin(row[-1]).count("1") == 8 - PADDING_BITS


def test_the_leftmost_pixel_of_a_row_is_the_top_bit_of_its_first_byte():
    # Most significant bit leftmost. Reversed, every row is mirrored in blocks
    # of eight, which reads as a shifted and garbled screen rather than as a
    # clean horizontal flip - and so gets blamed on the ribbon.
    frame = panel_sized()
    frame.putpixel((0, 0), 0)

    assert to_panel_bytes(frame)[0] == 0b01111111


def test_rows_follow_each_other_with_no_gap_between_them():
    # A single black pixel at the start of the second row must land in the first
    # byte of the second row's worth of bytes, not somewhere inside the first.
    frame = panel_sized()
    frame.putpixel((0, 1), 0)
    packed = to_panel_bytes(frame)

    assert packed[BYTES_PER_ROW] == 0b01111111
    assert packed[:BYTES_PER_ROW] == bytes([0xFF]) * (BYTES_PER_ROW - 1) + bytes([0xC0])
