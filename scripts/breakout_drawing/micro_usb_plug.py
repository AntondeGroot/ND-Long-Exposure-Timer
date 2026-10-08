"""A micro-USB solder plug in 3D, seen from the front, above and to one side.

Modelled on the usual DIY plug: a metal shell with a trapezoid section and two spring
latches in its wide face, a black body behind it, and behind that a lower black ledge
with the five solder pads lying flat on top.

x runs along the plug towards its tip, y across it, z up out of the wide side. Seen from
the tip, wide side up, the pins run 5-4-3-2-1 from left to right; looking down on the
wide side with the tip pointing away, that puts pin 1 on the left, at positive y.
"""

from __future__ import annotations

from dataclasses import dataclass

from .projection import Face, Projection, Vector, box
from .svg import Canvas

SCALE = 27

SHELL_LENGTH, SHELL_WIDTH, SHELL_HEIGHT, NARROWING = 6.5, 7.0, 2.0, 0.8
BODY_LENGTH, BODY_WIDTH, BODY_BOTTOM, BODY_TOP = 3.5, 8.0, -0.5, 2.6
LEDGE_LENGTH, LEDGE_WIDTH, LEDGE_TOP = 3.0, 7.4, 1.0
PAD_LENGTH, PAD_WIDTH, PAD_PITCH, PAD_INSET = 2.3, 0.8, 1.35, 0.2
PINS = 5
LEDGE_BACK = -BODY_LENGTH - LEDGE_LENGTH

SHELL_TOP, SHELL_SIDE, SHELL_END = "#e9ecef", "#ced4da", "#adb5bd"
OPENING = "#212529"
BLACK_TOP, BLACK_SIDE, BLACK_END = "#495057", "#343a40", "#2b2f33"
PAD_USED, PAD_UNUSED = "#e9c46a", "#dee2e6"
SLOT, SPRING = "#495057", "#f8f9fa"


def pin_y(pin: int) -> float:
    """Pin 1 on the left of the wide side, seen with the tip pointing away: positive y."""
    return ((PINS + 1) / 2 - pin) * PAD_PITCH


@dataclass(frozen=True)
class Plug:
    """Where the plug sits on the page: the screen point of the model's origin."""

    origin_x: float
    origin_y: float

    @property
    def _view(self) -> Projection:
        return Projection(self.origin_x, self.origin_y, SCALE)

    def pad_end(self, pin: int) -> tuple[float, float]:
        """Where a wire meets a pad: its back end, at the edge of the ledge."""
        return self._view.point((LEDGE_BACK + PAD_INSET + 0.3, pin_y(pin), LEDGE_TOP))

    def pad_label(self, pin: int) -> tuple[float, float]:
        """On the pad, between the wire's joint and the body: where its number goes."""
        return self._view.point((LEDGE_BACK + PAD_INSET + PAD_LENGTH * 0.62, pin_y(pin), LEDGE_TOP))

    def draw(self, canvas: Canvas, used_pins: set[int]) -> None:
        """Back to front along the plug - the viewer is in front of the tip - so nearer
        parts paint over further ones."""
        view = self._view
        for group in (_ledge_faces(), _pad_faces(used_pins), _body_faces(), _shell_faces()):
            view.paint(canvas, group)
        view.polygon(canvas, _opening(), OPENING)
        for slot, (spring_from, spring_to) in _latches():
            view.polygon(canvas, slot, SLOT)
            canvas.line(view.point(spring_from), view.point(spring_to), SPRING, 2.5)


def _shell_faces() -> list[Face]:
    """A prism with a trapezoid section: wide at the top, narrower underneath."""
    wide, narrow = SHELL_WIDTH / 2, SHELL_WIDTH / 2 - NARROWING
    x0, x1, z0, z1 = 0.0, SHELL_LENGTH, 0.0, SHELL_HEIGHT
    return [
        Face(((x0, -wide, z1), (x1, -wide, z1), (x1, wide, z1), (x0, wide, z1)), SHELL_TOP),
        Face(((x0, -narrow, z0), (x0, narrow, z0), (x1, narrow, z0), (x1, -narrow, z0)), SHELL_SIDE),
        Face(((x0, -narrow, z0), (x1, -narrow, z0), (x1, -wide, z1), (x0, -wide, z1)), SHELL_SIDE),
        Face(((x0, narrow, z0), (x0, wide, z1), (x1, wide, z1), (x1, narrow, z0)), SHELL_SIDE),
        Face(((x1, -narrow, z0), (x1, narrow, z0), (x1, wide, z1), (x1, -wide, z1)), SHELL_END),
    ]


def _opening() -> tuple[Vector, ...]:
    """The slot at the tip, the same trapezoid as the shell but smaller."""
    x, wall = SHELL_LENGTH + 0.01, 0.35
    wide = SHELL_WIDTH / 2 - wall
    narrow = SHELL_WIDTH / 2 - NARROWING - wall * 0.6
    return (x, -narrow, wall), (x, narrow, wall), (x, wide, SHELL_HEIGHT - wall), (x, -wide, SHELL_HEIGHT - wall)


def _latches() -> list[tuple[tuple[Vector, ...], tuple[Vector, Vector]]]:
    """The two long slots in the wide face, each with its spring: what marks the wide side."""
    x0, x1, z = 1.2, 5.0, SHELL_HEIGHT + 0.01
    latches = []
    for y in (-2.3, 2.3):
        slot = ((x0, y - 0.3, z), (x1, y - 0.3, z), (x1, y + 0.3, z), (x0, y + 0.3, z))
        latches.append((slot, ((x0 + 0.5, y, z), (x1 - 0.3, y, z))))
    return latches


def _body_faces() -> list[Face]:
    half = BODY_WIDTH / 2
    return box(-BODY_LENGTH, 0.0, -half, half, BODY_BOTTOM, BODY_TOP, BLACK_TOP, BLACK_SIDE, BLACK_END)


def _ledge_faces() -> list[Face]:
    half = LEDGE_WIDTH / 2
    return box(LEDGE_BACK, -BODY_LENGTH, -half, half, BODY_BOTTOM, LEDGE_TOP, BLACK_TOP, BLACK_SIDE, BLACK_END)


def _pad_faces(used_pins: set[int]) -> list[Face]:
    """The pads lie flat on the ledge, so each is one face just above its top."""
    x0, x1, z = LEDGE_BACK + PAD_INSET, LEDGE_BACK + PAD_INSET + PAD_LENGTH, LEDGE_TOP + 0.01
    faces = []
    for pin in range(1, PINS + 1):
        y, half = pin_y(pin), PAD_WIDTH / 2
        fill = PAD_USED if pin in used_pins else PAD_UNUSED
        faces.append(Face(((x0, y - half, z), (x1, y - half, z), (x1, y + half, z), (x0, y + half, z)), fill))
    return faces
