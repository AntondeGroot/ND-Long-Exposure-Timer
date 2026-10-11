"""Tests for the drawing pieces the screens share."""

from PIL import ImageDraw

from nd_timer.ui import render


def a_selected_row(value: str, carets: bool) -> bytes:
    frame = render.blank_frame()
    render.draw_value_row(ImageDraw.Draw(frame), 0, "MODE", value, selected=True, carets=carets)
    return frame.tobytes()


def test_a_value_too_long_for_its_carets_is_drawn_without_them():
    # Carets beside GHOST CROWD would run into the label, so the row goes without
    # them rather than crushing the name. A name that fits keeps them.
    assert a_selected_row("GHOST CROWD", carets=True) == a_selected_row("GHOST CROWD", carets=False)
    assert a_selected_row("WATERFALL", carets=True) != a_selected_row("WATERFALL", carets=False)
