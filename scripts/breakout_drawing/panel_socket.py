"""Panel-mount sockets in 3D: a flange with the opening, a black body, snap-in wedges, wires.

The flange sits on the outside of the enclosure wall; the body goes through the wall and
the wedges hold it there. The wires come out of the back. Both sockets in the build -
USB-C for power, USB-A for the camera - are this one shape with different sizes and a
different opening.

y runs from the front face (at y = 0, facing the viewer) back through the wall; x is
across the opening, z up.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .projection import EDGE, Face, Projection, prism_along_y, rounded_rect, stadium
from .svg import Canvas

FRONT, SIDE, TOP = "#3d4246", "#25292c", "#4a5056"
HOLE, TONGUE, METAL, CONTACT = "#0b0c0d", "#6c757d", "#ced4da", "#e9c46a"

Outline = list[tuple[float, float]]


@dataclass(frozen=True)
class SocketSpec:
    name: str
    scale: float
    flange: Outline
    flange_depth: float
    body_width: float
    body_height: float
    body_back: float
    wire_x: dict[str, float]
    opening: Callable[[Projection, Canvas], None]


@dataclass(frozen=True)
class PanelSocket:
    spec: SocketSpec
    origin_x: float
    origin_y: float

    @property
    def _view(self) -> Projection:
        return Projection(self.origin_x, self.origin_y, self.spec.scale)

    def wire_exit(self, wire: str, extra: float = 0.0) -> tuple[float, float]:
        """Where a wire leaves the back of the body, or `extra` further back along it."""
        return self._view.point((self.spec.wire_x[wire], self.spec.body_back + extra, 0.0))

    def draw(self, canvas: Canvas) -> None:
        """Back to front: the body and its wedges, then the flange, then the opening."""
        spec, view = self.spec, self._view
        view.paint(canvas, _body_faces(spec) + _wedge_faces(spec, 1) + _wedge_faces(spec, -1))
        view.paint(canvas, prism_along_y(spec.flange, 0.0, spec.flange_depth, FRONT, SIDE), stroke="none")
        view.polygon(canvas, tuple((x, 0.0, z) for x, z in spec.flange), FRONT, stroke=EDGE)
        spec.opening(view, canvas)


def _on_front(outline: Outline, z_offset: float = 0.0, lift: float = 0.01) -> tuple:
    """An outline drawn on the front face, `lift` in front of it so it paints on top."""
    return tuple((x, -lift, z + z_offset) for x, z in outline)


def _usb_c_opening(view: Projection, canvas: Canvas) -> None:
    view.polygon(canvas, _on_front(stadium(8.6, 2.8)), HOLE)
    view.polygon(canvas, _on_front(stadium(6.0, 0.7, 4), lift=0.02), TONGUE)


def _usb_a_opening(view: Projection, canvas: Canvas) -> None:
    """The metal-lined slot with the plastic tongue across its top half and the contacts
    under it."""
    view.polygon(canvas, _on_front(rounded_rect(13.2, 5.8, 0.4)), METAL)
    view.polygon(canvas, _on_front(rounded_rect(12.4, 5.0, 0.3), lift=0.02), HOLE)
    view.polygon(canvas, _on_front(rounded_rect(10.6, 1.9, 0.2), z_offset=1.0, lift=0.03), SIDE)
    for x in (-3.6, -1.2, 1.2, 3.6):
        contact = [(x - 0.7, -0.2), (x + 0.7, -0.2), (x + 0.7, 0.2), (x - 0.7, 0.2)]
        view.polygon(canvas, _on_front(contact, z_offset=-0.15, lift=0.04), CONTACT)


USB_C = SocketSpec(
    name="USB-C socket", scale=16,
    flange=stadium(13.0, 8.0), flange_depth=2.0,  # well proud of the body: the lip against the wall
    body_width=9.2, body_height=5.2, body_back=8.6,
    wire_x={"red": -1.4, "black": 1.4},
    opening=_usb_c_opening,
)

USB_A = SocketSpec(
    name="USB-A socket", scale=11,
    flange=rounded_rect(18.0, 11.0, 1.6), flange_depth=2.2,
    body_width=15.0, body_height=8.6, body_back=13.0,
    wire_x={"red": -3.0, "white": -1.0, "blue": 1.0, "black": 3.0},
    opening=_usb_a_opening,
)


def _body_faces(spec: SocketSpec) -> list[Face]:
    """A box behind the flange, from its back face to the end where the wires come out."""
    x, z = spec.body_width / 2, spec.body_height / 2
    faces = prism_along_y([(x, -z), (x, z), (-x, z), (-x, -z)], spec.flange_depth, spec.body_back, SIDE, SIDE)
    return [Face(f.corners, TOP if all(c[2] == z for c in f.corners) else f.fill) for f in faces]


def _wedge_faces(spec: SocketSpec, side: int) -> list[Face]:
    """A snap-in wedge on one side of the body: proud at the front, flush at the back."""
    x0, x1 = side * spec.body_width / 2, side * (spec.body_width / 2 + 0.8)
    y0 = spec.flange_depth + 1.0
    y1, h = y0 + 3.0, spec.body_height * 0.23
    front = ((x0, y0, -h), (x1, y0, -h), (x1, y0, h), (x0, y0, h))
    slope = ((x1, y0, -h), (x0, y1, -h), (x0, y1, h), (x1, y0, h))
    top = ((x0, y0, h), (x1, y0, h), (x0, y1, h))
    bottom = ((x0, y0, -h), (x0, y1, -h), (x1, y0, -h))
    if side < 0:
        front, slope, top, bottom = (tuple(reversed(face)) for face in (front, slope, top, bottom))
    return [Face(front, SIDE), Face(slope, SIDE), Face(top, TOP), Face(bottom, SIDE)]
