"""The 8-wire JST cable: as it arrives, cut in half, and made into a plug-and-socket pair.

It arrives with all eight wires on the male side and the female side loose. Cutting
every wire in half and soldering the cut ends to the female side gives a cable that
comes apart in the middle with the colours running straight through, so the lid with
the buttons can come off the board.
"""

from __future__ import annotations

from . import geometry as g
from .layout import JST_CABLE
from .parts import place
from .svg import Canvas

COLOURS = [wire.colour for wire in JST_CABLE]

WIDTH, HEIGHT = 1200, 960
SPACING = 18
OUTLINE = "#555"
HOUSING = "#f1f3f5"
TIN = "#adb5bd"
HEAT_SHRINK = "#343a40"
CUT = "#e03131"

PANEL_TOPS = (160, 430, 700)
MALE_X, CONNECTOR_WIDTH = 120, 50
WIRE_END_X = 900
FEMALE_LOOSE_X = 1010
CUT_X = 535


def jst_cable_page() -> str:
    canvas = Canvas(WIDTH, HEIGHT)
    canvas.text((40, 60), "The JST cable: cut it in half, solder the halves to the loose connector", 30, bold=True)
    canvas.text((40, 98), "Same colour on the same pin on both sides, so the colours run straight through.", 21, "#444")
    _as_delivered(canvas, PANEL_TOPS[0])
    _cut(canvas, PANEL_TOPS[1])
    _soldered(canvas, PANEL_TOPS[2])
    return canvas.svg()


def _as_delivered(canvas: Canvas, top: float) -> None:
    _panel_title(canvas, top, "As it arrives: all eight wires on the male connector, the female one loose")
    _male(canvas, MALE_X, top, mating_face_right=False)
    _wires(canvas, MALE_X + CONNECTOR_WIDTH, WIRE_END_X, top)
    _tinned_ends(canvas, WIRE_END_X, top, pointing_right=True)
    _female_loose(canvas, FEMALE_LOOSE_X, top)


def _cut(canvas: Canvas, top: float) -> None:
    _panel_title(canvas, top, "1. Cut every wire in half")
    _male(canvas, MALE_X, top, mating_face_right=False)
    _wires(canvas, MALE_X + CONNECTOR_WIDTH, WIRE_END_X, top)
    _tinned_ends(canvas, WIRE_END_X, top, pointing_right=True)
    _female_loose(canvas, FEMALE_LOOSE_X, top)
    y0, y1 = _wire_y(top, 0) - 22, _wire_y(top, len(COLOURS) - 1) + 22
    canvas.add(f'<line x1="{CUT_X}" y1="{y0}" x2="{CUT_X}" y2="{y1}" stroke="{CUT}" stroke-width="4" '
               'stroke-dasharray="10 7"/>')
    canvas.text((CUT_X, y1 + 26), "cut here", 20, CUT, anchor="middle", bold=True)


def _soldered(canvas: Canvas, top: float) -> None:
    _panel_title(canvas, top, "2. Plug the female onto the male, then solder each cut end to the pin facing "
                              "its colour and heat-shrink it")
    free_x, male_x = 200, 470
    female_x = male_x + CONNECTOR_WIDTH
    joint_x = female_x + CONNECTOR_WIDTH + 14
    _tinned_ends(canvas, free_x, top, pointing_right=False)
    _wires(canvas, free_x, male_x, top)
    _male(canvas, male_x, top, mating_face_right=True)
    _female(canvas, female_x, top)
    _wires(canvas, joint_x, WIRE_END_X, top)
    _heat_shrink(canvas, joint_x, top)
    _tinned_ends(canvas, WIRE_END_X, top, pointing_right=True)
    _destinations(canvas, top, board_x=free_x - 30, buttons_x=WIRE_END_X + 32)
    below = _wire_y(top, len(COLOURS) - 1) + 40
    canvas.text((female_x, below), "male + female", 19, "#444", anchor="middle")


def _destinations(canvas: Canvas, top: float, board_x: float, buttons_x: float) -> None:
    """Where each colour goes: its hole on the breakout board, and its button."""
    heading_y = _wire_y(top, 0) - 22
    canvas.text((board_x, heading_y), "breakout board", 16, "#444", anchor="end", bold=True)
    canvas.text((buttons_x, heading_y), "buttons", 16, "#444", bold=True)
    for i, wire in enumerate(JST_CABLE):
        y = _wire_y(top, i) + 5
        hole = place(wire.at) if wire.at in g.PADS else f"{wire.at}, GND rail"
        canvas.text((board_x, y), hole, 15, "#222", anchor="end")
        canvas.text((buttons_x, y), wire.button, 15, "#222")


def _panel_title(canvas: Canvas, top: float, title: str) -> None:
    canvas.text((40, top), title, 22, bold=True)


def _wire_y(top: float, index: int) -> float:
    return top + 50 + index * SPACING


def _wires(canvas: Canvas, x0: float, x1: float, top: float) -> None:
    for i, colour in enumerate(COLOURS):
        y = _wire_y(top, i)
        canvas.line((x0, y), (x1, y), OUTLINE, 11)
        canvas.line((x0, y), (x1, y), colour, 8)


def _tinned_ends(canvas: Canvas, x: float, top: float, pointing_right: bool) -> None:
    tip = x + 22 if pointing_right else x - 22
    for i in range(len(COLOURS)):
        y = _wire_y(top, i)
        canvas.line((x, y), (tip, y), TIN, 3)


def _connector_body(canvas: Canvas, x: float, top: float) -> tuple[float, float]:
    y0, y1 = _wire_y(top, 0) - 16, _wire_y(top, len(COLOURS) - 1) + 16
    canvas.rect(x, y0, CONNECTOR_WIDTH, y1 - y0, HOUSING, rx=4, stroke=OUTLINE, stroke_width=2)
    return y0, y1


def _male(canvas: Canvas, x: float, top: float, mating_face_right: bool) -> None:
    """The sockets face away from the wires: that is the side the female plugs into."""
    y0, _ = _connector_body(canvas, x, top)
    socket_x = x + 30 if mating_face_right else x + 6
    for i in range(len(COLOURS)):
        canvas.rect(socket_x, _wire_y(top, i) - 5, 14, 10, "#ced4da", stroke=OUTLINE, stroke_width=1)
    canvas.text((x + CONNECTOR_WIDTH / 2, y0 - 8), "male", 17, "#444", anchor="middle", bold=True)
    pin_one_x = x + 4 if mating_face_right else x + 34
    canvas.text((pin_one_x, _wire_y(top, 0) + 5), "1", 13, "#444")


def _female(canvas: Canvas, x: float, top: float) -> None:
    y0, _ = _connector_body(canvas, x, top)
    for i in range(len(COLOURS)):
        y = _wire_y(top, i)
        canvas.line((x + CONNECTOR_WIDTH, y), (x + CONNECTOR_WIDTH + 14, y), TIN, 4)
    canvas.text((x + CONNECTOR_WIDTH / 2, y0 - 8), "female", 17, "#444", anchor="middle", bold=True)


def _female_loose(canvas: Canvas, x: float, top: float) -> None:
    _female(canvas, x, top)
    canvas.text((x + CONNECTOR_WIDTH / 2, _wire_y(top, len(COLOURS) - 1) + 40), "loose", 17, "#444",
                anchor="middle")


def _heat_shrink(canvas: Canvas, x: float, top: float) -> None:
    for i in range(len(COLOURS)):
        y = _wire_y(top, i)
        canvas.rect(x - 6, y - 7, 34, 14, HEAT_SHRINK, rx=3)
