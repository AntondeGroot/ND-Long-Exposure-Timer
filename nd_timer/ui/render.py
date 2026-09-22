"""Drawing the screens into a 1-bit buffer the panel can take.

Everything is drawn in mode "1", which is what the panel wants and also means
Pillow does no antialiasing - so what is rendered here is exactly what appears,
and a golden-image test is a true comparison rather than an approximate one.
"""

from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from nd_timer.ui import layout
from nd_timer.ui.layout import BLACK, HEIGHT, WHITE, WIDTH


@lru_cache(maxsize=8)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def regular(size: int) -> ImageFont.FreeTypeFont:
    return _font(str(layout.REGULAR_FONT), size)


def bold(size: int) -> ImageFont.FreeTypeFont:
    return _font(str(layout.BOLD_FONT), size)


def blank_frame() -> Image.Image:
    return Image.new("1", (WIDTH, HEIGHT), WHITE)


def draw_centred(draw: ImageDraw.ImageDraw, centre_x, y, text, font, fill=BLACK) -> None:
    """Centre horizontally, with `y` the top of the text."""
    width = draw.textlength(text, font=font)
    draw.text((centre_x - width / 2, y), text, font=font, fill=fill)


def draw_centred_in(draw: ImageDraw.ImageDraw, centre_x, centre_y, text, font, fill=BLACK) -> None:
    """Centre on a point in both axes.

    Large text is placed by the middle of the space it has to live in, because
    guessing a baseline from the font size is how the hero time ended up
    overlapping the status pill.
    """
    draw.text((centre_x, centre_y), text, font=font, fill=fill, anchor="mm")


def largest_font_that_fits(draw: ImageDraw.ImageDraw, text: str, max_width: int, sizes) -> ImageFont.FreeTypeFont:
    """The biggest of `sizes` that keeps `text` inside `max_width`.

    The answer is anything from "1.1 s" to "12m 30s", and a column 122px wide has
    no slack, so the type has to fit the number rather than the other way round.
    """
    for size in sizes:
        font = bold(size)
        if draw.textlength(text, font=font) <= max_width:
            return font
    return bold(sizes[-1])


def draw_fitted(draw: ImageDraw.ImageDraw, centre_x, centre_y, text, max_width, sizes, fill=BLACK) -> None:
    font = largest_font_that_fits(draw, text, max_width, sizes)
    draw.text((centre_x, centre_y), text, font=font, fill=fill, anchor="mm")


def draw_right_aligned_fitted(
    draw: ImageDraw.ImageDraw, right_x, y, text, max_width, sizes, fill=BLACK
) -> None:
    """Right-align `text`, shrinking it until it fits `max_width`."""
    font = largest_font_that_fits(draw, text, max_width, sizes)
    width = draw.textlength(text, font=font)
    draw.text((right_x - width, y), text, font=font, fill=fill)


def draw_inverted_bar(draw: ImageDraw.ImageDraw, box) -> None:
    """A filled black bar: the only way to say "selected" on a one-bit panel."""
    draw.rectangle(box, fill=BLACK)


def draw_status_bar(
    draw: ImageDraw.ImageDraw, left: str, battery: int | None, tag: str = ""
) -> None:
    """The sync note, an optional tag and the battery. A title would not fit too."""
    draw.text((2, 2), left, font=regular(layout.TINY), fill=BLACK)
    _draw_status_tag(draw, tag)

    # A battery drawn rather than written: it reads faster and costs less width.
    body = (WIDTH - 26, 3, WIDTH - 8, 12)
    draw.rectangle(body, outline=BLACK)
    draw.rectangle((WIDTH - 8, 6, WIDTH - 6, 9), fill=BLACK)

    if battery is None:
        _draw_unknown_charge(draw, body)
    else:
        fill_width = int((body[2] - body[0] - 2) * max(0, min(100, battery)) / 100)
        if fill_width:
            draw.rectangle((body[0] + 1, body[1] + 1, body[0] + fill_width, body[3] - 1), fill=BLACK)

    draw.line((0, layout.STATUS_BAR_HEIGHT, WIDTH, layout.STATUS_BAR_HEIGHT), fill=BLACK)


def _draw_unknown_charge(draw: ImageDraw.ImageDraw, body) -> None:
    """Hatched, because an unknown battery must not look like a flat one.

    There is no gauge answering - no UPS fitted, or the bus is not up - and an
    empty outline would say the cell is dead, which is a worse lie on a device
    you take out at dusk than admitting the number is not known.
    """
    for x in range(body[0] + 1, body[2]):
        for y in range(body[1] + 1, body[3]):
            if (x + y) % 2 == 0:
                draw.point((x, y), fill=BLACK)


def _draw_status_tag(draw: ImageDraw.ImageDraw, tag: str) -> None:
    """A word tucked in beside the battery, where the eye already goes for state."""
    if not tag:
        return

    font = regular(layout.TINY)
    width = draw.textlength(tag, font=font)
    draw.text((layout.STATUS_TAG_RIGHT_X - width, 2), tag, font=font, fill=BLACK)


def draw_banner_footer(draw: ImageDraw.ImageDraw, text: str, selected: bool = True) -> None:
    """One bar across the whole width, for a screen with a single action.

    Where the action is a stop the five-way walks to, the bar is only inverted
    while it holds the selection - the same idiom as every row above it.
    """
    # The same band on every screen, so the footer does not jump about as they
    # change.
    top = layout.FOOTER_TOP
    if selected:
        draw.rectangle((0, top, WIDTH, HEIGHT), fill=BLACK)
    else:
        draw.line((0, top, WIDTH, top), fill=BLACK)
    ink = WHITE if selected else BLACK
    draw_centred(draw, WIDTH // 2, top + 6, text, bold(layout.SMALL), fill=ink)


def draw_value_row(
    draw: ImageDraw.ImageDraw, top: int, label: str, value: str, selected: bool, carets: bool = True
) -> None:
    """A label and its value on one line, inverted when it holds the selection.

    Both of the device's lists are this row - the calculator's working and the
    settings - so it lives here rather than with either of them.
    """
    ink = WHITE if selected else BLACK
    if selected:
        draw_inverted_bar(draw, (0, top, WIDTH, top + layout.ROW_HEIGHT - 2))

    label_font = regular(layout.TINY)
    draw.text((layout.LABEL_X, top + 4), label, font=label_font, fill=ink)

    # Carets appear only on the selected row: they say left and right change it,
    # so a row they do nothing on goes without.
    text = f"< {value} >" if selected and carets else value

    # Whatever is left once the label has had its say.
    label_width = draw.textlength(label, font=label_font)
    available = layout.VALUE_RIGHT_X - layout.LABEL_X - label_width - layout.LABEL_VALUE_GAP

    draw_right_aligned_fitted(
        draw, layout.VALUE_RIGHT_X, top + 3, text, available, layout.ROW_VALUE_SIZES, fill=ink,
    )
