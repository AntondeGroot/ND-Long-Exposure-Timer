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
    off_by: str
    selected: str
    base_shutter: str
    final_time: str
    setting_time: bool
    shows_nudge_hint: bool
    time_is_set: bool
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
class DelayScreen:
    """The frame between the press and the shutter. Nothing on it moves."""

    mode: str
    exposure: str
    delay: str
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

    render.draw_status_bar(draw, screen.synced_note, screen.battery, _hand_set_tag(screen))
    _draw_answer(draw, screen)
    _draw_parameter_list(draw, screen)
    render.draw_footer(draw, selected=screen.selected)
    return frame


def _hand_set_tag(screen: MainScreen) -> str:
    """The status bar says when the answer is no longer the calculator's.

    Without it the panel would show a time that quietly contradicts the working
    printed underneath it.
    """
    return "SET" if screen.time_is_set else ""


def _draw_answer(draw: ImageDraw.ImageDraw, screen: MainScreen) -> None:
    """The exposure, given the top of the screen and the largest type.

    It is the only thing here worth reading at arm's length; everything below is
    the working that produced it - and it is also the one value the photographer
    can take over, so this is where the selection and the setting arrows show.
    """
    ink = WHITE if screen.setting_time else BLACK

    _draw_answer_box(draw, screen)
    _draw_final_time(draw, screen, ink)
    _draw_target_or_hint(draw, screen, ink)
    _draw_bulb_badge(draw, layout.CENTRE_X, screen, ink)
    draw.line((0, layout.ANSWER_BOTTOM, WIDTH, layout.ANSWER_BOTTOM), fill=BLACK)


def _draw_answer_box(draw: ImageDraw.ImageDraw, screen: MainScreen) -> None:
    """Outlined when the five-way points at the time, filled while it is set."""
    if screen.setting_time:
        render.draw_inverted_bar(draw, layout.ANSWER_BOX)
        return
    if screen.selected == layout.TIME:
        draw.rectangle(layout.ANSWER_BOX, outline=BLACK)


def _draw_final_time(draw: ImageDraw.ImageDraw, screen: MainScreen, ink: int) -> None:
    if screen.setting_time:
        _draw_setting_arrows(draw, ink)

    render.draw_fitted(
        draw, layout.CENTRE_X, layout.ANSWER_CENTRE_Y,
        screen.final_time, _answer_width(screen), layout.HERO_SIZES, fill=ink,
    )


def _answer_width(screen: MainScreen) -> int:
    """The arrows take the margins while the time is being set."""
    return layout.SETTING_MAX_WIDTH if screen.setting_time else layout.ANSWER_MAX_WIDTH


def _draw_setting_arrows(draw: ImageDraw.ImageDraw, ink: int) -> None:
    """Left and right, flanking the number they move."""
    font = render.bold(layout.MEDIUM)
    draw.text((layout.SETTING_ARROW_X, layout.ANSWER_CENTRE_Y), "\u25c0", font=font, fill=ink, anchor="lm")
    draw.text((WIDTH - layout.SETTING_ARROW_X, layout.ANSWER_CENTRE_Y), "\u25b6", font=font, fill=ink, anchor="rm")


def _draw_target_or_hint(draw: ImageDraw.ImageDraw, screen: MainScreen, ink: int) -> None:
    """The line under the time: what the subject wants, or what up and down do.

    While the time is being set the target has nothing to say - the photographer
    has already decided - and the line is worth more as the other half of the
    controls, since arrows alone would not say that seconds are a press away.

    Down at the fast end a second is three stops, which is a jump rather than an
    adjustment. The press still works - it is often how you leave the fast end -
    but the line stays empty rather than offering it as a fine control.
    """
    if not screen.setting_time:
        _draw_target(draw, layout.CENTRE_X, screen)
        return
    if not screen.shows_nudge_hint:
        return

    render.draw_centred(
        draw, layout.CENTRE_X, layout.TARGET_Y, "\u25b2\u25bc 1s", render.regular(layout.TINY), fill=ink
    )


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


def _draw_bulb_badge(draw: ImageDraw.ImageDraw, centre: int, screen: MainScreen, ink: int) -> None:
    """Bulb is worth shouting about: it means the Pi is doing the timing.

    The pill is an inversion of whatever it sits on, so it keeps shouting once
    the answer around it has been inverted for setting.
    """
    if not screen.is_bulb:
        return

    font = render.bold(layout.TINY)
    width = draw.textlength("BULB", font=font) + layout.PILL_PADDING
    draw.rectangle(
        (centre - width / 2, layout.PILL_TOP, centre + width / 2, layout.PILL_TOP + layout.PILL_HEIGHT),
        fill=ink,
    )
    render.draw_centred(draw, centre, layout.PILL_TOP + 2, "BULB", font, fill=_behind(ink))


def _behind(ink: int) -> int:
    """The other of the panel's two colours - the one this ink is legible on."""
    return WHITE if ink == BLACK else BLACK


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
        "off": screen.off_by,
        "MODE": screen.mode,
    }

    for row, (label, is_selectable) in enumerate(layout.ROW_PLAN):
        selected = is_selectable and label == screen.selected
        render.draw_value_row(draw, layout.row_top(row), label, values[label], selected)


def render_delay(screen: DelayScreen):
    """Drawn once when SHOOT is pressed, and left alone until the shutter opens.

    Nothing here counts down. The panel takes about a second to redraw and wears
    a little each time, so a ticking number would spend the delay flashing -
    through the very seconds the delay exists to keep still - and would be out
    of date by the time it had finished drawing itself.

    So it says the two things that are worth saying once: this is the exposure
    that is coming, and this is why it has not started yet.
    """
    frame = render.blank_frame()
    draw = ImageDraw.Draw(frame)

    render.draw_status_bar(draw, screen.mode.upper(), screen.battery)

    render.draw_fitted(
        draw, layout.CENTRE_X, 66, screen.exposure, layout.ANSWER_MAX_WIDTH, layout.HERO_SIZES
    )
    badge = "BULB" if screen.is_bulb else "TIMED"
    render.draw_centred(draw, layout.CENTRE_X, 100, badge, render.bold(layout.SMALL))

    render.draw_centred(
        draw, layout.CENTRE_X, 140, f"{screen.delay} delay before", render.regular(layout.SMALL)
    )
    render.draw_centred(draw, layout.CENTRE_X, 156, "exposure begins", render.regular(layout.SMALL))

    render.draw_banner_footer(draw, "HOLD TO CANCEL")
    return frame


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
