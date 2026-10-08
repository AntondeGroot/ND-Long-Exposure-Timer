"""A panel-mount USB-C socket in 3D: rounded flange, black body, snap-in wedges, two wires.

The flange sits on the outside of the enclosure wall with the USB-C opening in it; the
body goes through the wall and the wedges hold it there. The red and black wires come
out of the back.

y runs from the front face (at y = 0, facing the viewer) back through the wall; x is
across the opening, z up.
"""

from __future__ import annotations

from dataclasses import dataclass

from .projection import EDGE, Face, Projection, prism_along_y, stadium
from .svg import Canvas

SCALE = 16

# The flange stands well proud of the body all round: the lip that sits against the wall.
FLANGE_WIDTH, FLANGE_HEIGHT, FLANGE_DEPTH = 13.0, 8.0, 2.0
BODY_WIDTH, BODY_HEIGHT, BODY_BACK = 9.2, 5.2, 8.6
OPENING_WIDTH, OPENING_HEIGHT = 8.6, 2.8
TONGUE_WIDTH, TONGUE_HEIGHT = 6.0, 0.7
WEDGE_FROM, WEDGE_TO, WEDGE_OUT, WEDGE_HALF_HEIGHT = 2.6, 5.6, 0.8, 1.2
WIRE_X = {"red": -1.4, "black": 1.4}

FRONT, SIDE, TOP = "#3d4246", "#25292c", "#4a5056"
OPENING, TONGUE = "#0b0c0d", "#6c757d"


@dataclass(frozen=True)
class Socket:
    origin_x: float
    origin_y: float

    @property
    def _view(self) -> Projection:
        return Projection(self.origin_x, self.origin_y, SCALE)

    def wire_exit(self, colour: str, extra: float = 0.0) -> tuple[float, float]:
        """Where a wire leaves the back of the body, or `extra` further back along it."""
        return self._view.point((WIRE_X[colour], BODY_BACK + extra, 0.0))

    def draw(self, canvas: Canvas) -> None:
        """Back to front: the body and its wedges, then the flange, then the opening."""
        view = self._view
        view.paint(canvas, _body_faces() + _wedge_faces(1) + _wedge_faces(-1))
        outline = stadium(FLANGE_WIDTH, FLANGE_HEIGHT)
        view.paint(canvas, prism_along_y(outline, 0.0, FLANGE_DEPTH, FRONT, SIDE), stroke="none")
        view.polygon(canvas, tuple((x, 0.0, z) for x, z in outline), FRONT, stroke=EDGE)
        view.polygon(canvas, tuple((x, -0.01, z) for x, z in stadium(OPENING_WIDTH, OPENING_HEIGHT)), OPENING)
        view.polygon(canvas, tuple((x, -0.02, z) for x, z in stadium(TONGUE_WIDTH, TONGUE_HEIGHT, 4)), TONGUE)


def _body_faces() -> list[Face]:
    """A box behind the flange, from its back face to the end where the wires come out."""
    x, z = BODY_WIDTH / 2, BODY_HEIGHT / 2
    outline = [(x, -z), (x, z), (-x, z), (-x, -z)]
    faces = prism_along_y(outline, FLANGE_DEPTH, BODY_BACK, SIDE, SIDE)
    return [Face(f.corners, TOP if all(c[2] == z for c in f.corners) else f.fill) for f in faces]


def _wedge_faces(side: int) -> list[Face]:
    """A snap-in wedge on one side of the body: proud at the front, flush at the back."""
    x0, x1 = side * BODY_WIDTH / 2, side * (BODY_WIDTH / 2 + WEDGE_OUT)
    y0, y1, h = WEDGE_FROM, WEDGE_TO, WEDGE_HALF_HEIGHT
    front = ((x0, y0, -h), (x1, y0, -h), (x1, y0, h), (x0, y0, h))
    slope = ((x1, y0, -h), (x0, y1, -h), (x0, y1, h), (x1, y0, h))
    top = ((x0, y0, h), (x1, y0, h), (x0, y1, h))
    bottom = ((x0, y0, -h), (x0, y1, -h), (x1, y0, -h))
    if side < 0:
        front, slope, top, bottom = (tuple(reversed(face)) for face in (front, slope, top, bottom))
    return [Face(front, SIDE), Face(slope, SIDE), Face(top, TOP), Face(bottom, SIDE)]
