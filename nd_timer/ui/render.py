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


def draw_status_bar(draw: ImageDraw.ImageDraw, left: str, battery: int) -> None:
    """The sync note and the battery. A title would not fit beside them."""
    draw.text((2, 2), left, font=regular(layout.TINY), fill=BLACK)

    # A battery drawn rather than written: it reads faster and costs less width.
    body = (WIDTH - 26, 3, WIDTH - 8, 12)
    draw.rectangle(body, outline=BLACK)
    draw.rectangle((WIDTH - 8, 6, WIDTH - 6, 9), fill=BLACK)
    fill_width = int((body[2] - body[0] - 2) * max(0, min(100, battery)) / 100)
    if fill_width:
        draw.rectangle((body[0] + 1, body[1] + 1, body[0] + fill_width, body[3] - 1), fill=BLACK)

    draw.line((0, layout.STATUS_BAR_HEIGHT, WIDTH, layout.STATUS_BAR_HEIGHT), fill=BLACK)


def draw_banner_footer(draw: ImageDraw.ImageDraw, text: str) -> None:
    """One inverted bar across the whole width, for a screen with a single action."""
    # Same height as SHOOT's bar on the calculator screen, so the footer does not
    # jump about as screens change.
    top = layout.SHOOT_TOP
    draw.rectangle((0, top, WIDTH, HEIGHT), fill=BLACK)
    draw_centred(draw, WIDTH // 2, top + 6, text, bold(layout.SMALL), fill=WHITE)


def draw_footer(draw: ImageDraw.ImageDraw, quiet=("MENU", "SYNC"), action="SHOOT") -> None:
    """Two bands: the quiet buttons share a row, the one with consequences gets its own."""
    top = layout.FOOTER_TOP
    draw.line((0, top, WIDTH, top), fill=BLACK)

    midpoint = WIDTH // 2
    draw.line((midpoint, top, midpoint, layout.SHOOT_TOP), fill=BLACK)
    for index, label in enumerate(quiet):
        centre = midpoint // 2 + index * midpoint
        draw_centred(draw, centre, top + 4, label, bold(layout.SMALL))

    draw.rectangle((0, layout.SHOOT_TOP, WIDTH, HEIGHT), fill=BLACK)
    draw_centred(draw, midpoint, layout.SHOOT_TOP + 5, action, bold(layout.MEDIUM), fill=WHITE)
