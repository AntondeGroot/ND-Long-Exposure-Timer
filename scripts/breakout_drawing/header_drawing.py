"""The last step on its own: the female 2x20 header under the breakout board.

Seen from low down, so the header hanging under the near edge shows: it plugs onto the
Pi, and its pins come up through the board to be soldered on top. The board is only
sketched - green, with its mounting holes and a field of pads - because the point is
which side the header goes on.

x runs along the board, y across it from the near edge, z up from its top face.
"""

from __future__ import annotations

import math

from .projection import EDGE, Face, Projection, Vector, box, prism_along_z, rounded_rect
from .svg import Canvas

WIDTH, HEIGHT = 1150, 600
VIEW: Vector = (-0.3, -0.85, 0.42)
SCALE = 11.5

BOARD_LENGTH, BOARD_WIDTH, BOARD_THICKNESS, CORNER_RADIUS = 65.0, 30.0, 1.6, 3.5
PITCH, COLUMNS = 2.54, 20
HEADER_Y, HEADER_HEIGHT = 3.5, 8.5
PIN_LENGTH = 6.0  # how far the header's pins stand up out of the top of the board
MOUNTING_HOLES = [(3.5, 3.5), (61.5, 3.5), (3.5, 26.5), (61.5, 26.5)]


def _centred(page_x: float, page_y: float) -> Projection:
    """A projection that puts the middle of the board at this point on the page."""
    middle_x, middle_y = Projection(0.0, 0.0, SCALE, VIEW).point((BOARD_LENGTH / 2, BOARD_WIDTH / 2, -3.0))
    return Projection(page_x - middle_x, page_y - middle_y, SCALE, VIEW)


VIEWPORT = _centred(WIDTH / 2, 330)

GREEN_TOP, GREEN_SIDE = "#1f6b48", "#17533a"
COPPER, DRILL, HOLE = "#d9b04a", "#1b1b1b", "#ffffff"
PLASTIC_TOP, PLASTIC_SIDE = "#343a40", "#212529"
SOLDER, PIN = "#ced4da", "#f1f3f5"


def header_page() -> str:
    canvas = Canvas(WIDTH, HEIGHT)
    canvas.text((40, 60), "Last: the 40-pin header", 30, bold=True)
    canvas.text((40, 98), "The female header goes underneath, where it plugs onto the Pi. Its pins come up through "
                "the board: solder them on top.", 19, "#444")
    VIEWPORT.paint(canvas, _header_body())
    _board(canvas)
    _flat_circles(canvas, _proto_pads(), 0.75, COPPER, DRILL)
    _flat_circles(canvas, MOUNTING_HOLES, 1.4, HOLE, None)
    _flat_circles(canvas, _pin_positions(), 0.85, SOLDER, None)
    furthest_first = sorted(_pin_positions(), key=lambda p: p[0] * VIEW[0] + p[1] * VIEW[1])
    for x, y in furthest_first:
        VIEWPORT.paint(canvas, box(x - 0.32, x + 0.32, y - 0.32, y + 0.32, 0.0, PIN_LENGTH, PIN, SOLDER, SOLDER))
    return canvas.svg()


def _columns() -> list[float]:
    return [BOARD_LENGTH / 2 + (i - (COLUMNS - 1) / 2) * PITCH for i in range(COLUMNS)]


def _pin_positions() -> list[tuple[float, float]]:
    return [(x, y) for x in _columns() for y in (HEADER_Y - PITCH / 2, HEADER_Y + PITCH / 2)]


def _board(canvas: Canvas) -> None:
    """A slab with rounded corners, like the Pi Zero it sits on. The rounded edge is many
    thin faces, outlined in their own colour so no seams show; the top gets a real outline."""
    outline = [(x + BOARD_LENGTH / 2, y + BOARD_WIDTH / 2)
               for x, y in rounded_rect(BOARD_LENGTH, BOARD_WIDTH, CORNER_RADIUS, points_per_corner=8)]
    VIEWPORT.paint(canvas, prism_along_z(outline, -BOARD_THICKNESS, 0.0, GREEN_TOP, GREEN_SIDE), stroke=GREEN_SIDE)
    VIEWPORT.polygon(canvas, tuple((x, y, 0.0) for x, y in outline), GREEN_TOP, stroke=EDGE)


def _header_body() -> list[Face]:
    x0, x1 = _columns()[0] - PITCH / 2, _columns()[-1] + PITCH / 2
    y0, y1 = HEADER_Y - PITCH, HEADER_Y + PITCH
    z1 = -BOARD_THICKNESS
    return box(x0, x1, y0, y1, z1 - HEADER_HEIGHT, z1, PLASTIC_TOP, PLASTIC_SIDE, PLASTIC_SIDE)


def _proto_pads() -> list[tuple[float, float]]:
    """A field of pads across the middle: enough to say 'this is the breakout board'."""
    columns = [8.0 + i * PITCH for i in range(20)]
    rows = [10.5 + j * PITCH for j in range(6)]
    return [(x, y) for x in columns for y in rows]


def _flat_circles(canvas: Canvas, centres: list[tuple[float, float]], radius: float, fill: str,
                  drill: str | None) -> None:
    for x, y in centres:
        VIEWPORT.polygon(canvas, _circle(x, y, radius), fill)
        if drill:
            VIEWPORT.polygon(canvas, _circle(x, y, radius * 0.45), drill)


def _circle(x: float, y: float, radius: float, points: int = 14) -> tuple[Vector, ...]:
    return tuple((x + radius * math.cos(2 * math.pi * i / points), y + radius * math.sin(2 * math.pi * i / points),
                  0.02) for i in range(points))
