"""The screens, drawn from a plain description of what they should show.

Each screen takes a small value object rather than the live application state, so
a screen can be rendered - and compared against a golden image - without a
camera, a panel, or a running exposure.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import ImageDraw

from nd_timer.ui import layout, render
from nd_timer.ui.layout import BLACK, HEIGHT, WHITE, WIDTH


@dataclass(frozen=True)
class MainScreen:
    """Everything the calculator screen shows."""

    mode: str
    iso: str
    aperture: str
    nd_label: str
    nd_stops: str
    selected_row: int
    base_shutter: str
    final_time: str
    target: str
    direction: int
    is_bulb: bool
    synced_note: str
    battery: int


@dataclass(frozen=True)
class CountdownScreen:
    """A running exposure."""

    mode: str
    remaining: str
    elapsed: str
    total: str
    progress: float
    is_bulb: bool
    battery: int


@dataclass(frozen=True)
class SplashScreen:
    """Shown while the Pi is still starting up."""

    message: str
    version: str


def render_splash(screen: SplashScreen):
    """The frame the panel holds while there is no software running yet.

    E-paper keeps its last image with no power, so this is on screen from the
    moment the device is switched on - long before anything could draw it.
    """
    frame = render.blank_frame()
    draw = ImageDraw.Draw(frame)

    render.draw_centred(draw, layout.CENTRE_X, 52, "ND", render.bold(36))
    render.draw_centred(draw, layout.CENTRE_X, 96, "LONG EXPOSURE", render.bold(layout.SMALL))
    render.draw_centred(draw, layout.CENTRE_X, 110, "TIMER", render.bold(layout.SMALL))

    draw.line((30, 134, WIDTH - 30, 134), fill=BLACK)

    render.draw_centred(draw, layout.CENTRE_X, 150, screen.message, render.regular(layout.SMALL))
    render.draw_centred(draw, layout.CENTRE_X, 226, screen.version, render.regular(layout.TINY))
    return frame


def render_main(screen: MainScreen):
    frame = render.blank_frame()
    draw = ImageDraw.Draw(frame)

    render.draw_status_bar(draw, screen.synced_note, screen.battery)
    _draw_answer(draw, screen)
    _draw_parameter_list(draw, screen)
    render.draw_footer(draw)
    return frame


def _draw_answer(draw: ImageDraw.ImageDraw, screen: MainScreen) -> None:
    """The computed exposure, given the top of the screen and the largest type.

    It is the only thing here worth reading at arm's length; everything below is
    the working that produced it.
    """
    render.draw_fitted(
        draw, layout.CENTRE_X, layout.ANSWER_CENTRE_Y,
        screen.final_time, layout.ANSWER_MAX_WIDTH, layout.HERO_SIZES,
    )
    _draw_target(draw, layout.CENTRE_X, screen)
    _draw_bulb_badge(draw, layout.CENTRE_X, screen)
    draw.line((0, layout.ANSWER_BOTTOM, WIDTH, layout.ANSWER_BOTTOM), fill=BLACK)


def _draw_target(draw: ImageDraw.ImageDraw, centre: int, screen: MainScreen) -> None:
    """What this subject wants, and which way to move if you are outside it.

    An arrow rather than a verdict: being told the exposure is wrong is not
    useful, knowing it needs to be longer is.
    """
    if not screen.target:
        return

    # Triangles rather than letters: at 9px a "v" reads as text, an arrow reads
    # as an instruction. DejaVu has both glyphs.
    arrow = {1: " ▲", -1: " ▼"}.get(screen.direction, "")
    render.draw_centred(
        draw, centre, layout.TARGET_Y, f"aim {screen.target}{arrow}", render.regular(layout.TINY)
    )


def _draw_bulb_badge(draw: ImageDraw.ImageDraw, centre: int, screen: MainScreen) -> None:
    """Bulb is worth shouting about: it means the Pi is doing the timing."""
    if not screen.is_bulb:
        return

    font = render.bold(layout.TINY)
    width = draw.textlength("BULB", font=font) + 12
    draw.rectangle(
        (centre - width / 2, layout.PILL_TOP, centre + width / 2, layout.PILL_TOP + layout.PILL_HEIGHT),
        fill=BLACK,
    )
    render.draw_centred(draw, centre, layout.PILL_TOP + 2, "BULB", font, fill=WHITE)


def _draw_parameter_list(draw: ImageDraw.ImageDraw, screen: MainScreen) -> None:
    """The working: one line per value, scanned rather than read.

    Derived rows are drawn the same as the rest but never take the selection, so
    the buttons only ever land on something they can actually change.
    """
    values = {
        "base": screen.base_shutter,
        "ISO": screen.iso,
        "APER": screen.aperture,
        "ND": screen.nd_label,
        "stops": screen.nd_stops,
        "MODE": screen.mode,
    }

    selectable_index = 0
    for row, (label, is_selectable) in enumerate(layout.ROW_PLAN):
        selected = False
        if is_selectable:
            selected = selectable_index == screen.selected_row
            selectable_index += 1

        _draw_row(draw, layout.row_top(row), label, values[label], selected)


def _draw_row(draw: ImageDraw.ImageDraw, top: int, label: str, value: str, selected: bool) -> None:
    ink = WHITE if selected else BLACK
    if selected:
        render.draw_inverted_bar(draw, (0, top, WIDTH, top + layout.ROW_HEIGHT - 2))

    label_font = render.regular(layout.TINY)
    draw.text((layout.LABEL_X, top + 4), label, font=label_font, fill=ink)

    # Carets appear only on the selected row: they say which buttons do something.
    text = f"< {value} >" if selected else value

    # Whatever is left once the label has had its say.
    label_width = draw.textlength(label, font=label_font)
    available = layout.VALUE_RIGHT_X - layout.LABEL_X - label_width - layout.LABEL_VALUE_GAP

    render.draw_right_aligned_fitted(
        draw, layout.VALUE_RIGHT_X, top + 3, text, available, layout.ROW_VALUE_SIZES, fill=ink,
    )


def render_countdown(screen: CountdownScreen):
    frame = render.blank_frame()
    draw = ImageDraw.Draw(frame)

    render.draw_status_bar(draw, screen.mode.upper(), screen.battery)

    badge = "BULB" if screen.is_bulb else "TIMED"
    render.draw_centred(draw, layout.CENTRE_X, 26, badge, render.bold(layout.SMALL))
    render.draw_centred(draw, layout.CENTRE_X, 48, "REMAINING", render.regular(layout.TINY))

    # The one number worth seeing from where the camera is standing.
    render.draw_centred_in(draw, layout.CENTRE_X, 100, screen.remaining, render.bold(layout.COUNTDOWN_HERO))

    _draw_progress_bar(draw, screen.progress)

    render.draw_centred(draw, layout.CENTRE_X, 160, f"{screen.elapsed} elapsed", render.regular(layout.SMALL))
    render.draw_centred(draw, layout.CENTRE_X, 176, f"of {screen.total}", render.regular(layout.SMALL))

    render.draw_banner_footer(draw, "HOLD TO CANCEL")
    return frame


def _draw_progress_bar(draw: ImageDraw.ImageDraw, progress: float) -> None:
    left, right = 10, WIDTH - 10
    top, bottom = 134, 148
    draw.rectangle((left, top, right, bottom), outline=BLACK)

    filled = int((right - left - 2) * max(0.0, min(1.0, progress)))
    if filled:
        draw.rectangle((left + 1, top + 1, left + filled, bottom - 1), fill=BLACK)
