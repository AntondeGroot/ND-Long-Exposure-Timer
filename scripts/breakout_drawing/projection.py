"""Flat-shaded 3D for the parts drawings: faces, one fixed viewpoint, and painting order.

Everything is drawn from the same direction, so parts drawn on one page agree with each
other. A face is a flat polygon wound so its normal points outwards; faces turned away
from the viewer are skipped, and the rest are painted far to near.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .svg import Canvas

Vector = tuple[float, float, float]
EDGE = "#555"

# Towards the viewer: from in front (positive x), from the left (negative y), and from
# above - roughly the angle of the usual product photo.
VIEW: Vector = (0.55, -0.6, 0.62)


def _normalise(v: Vector) -> Vector:
    length = math.sqrt(sum(c * c for c in v))
    return v[0] / length, v[1] / length, v[2] / length


def _cross(a: Vector, b: Vector) -> Vector:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _dot(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


TOWARDS_VIEWER = _normalise(VIEW)
_FORWARD = (-TOWARDS_VIEWER[0], -TOWARDS_VIEWER[1], -TOWARDS_VIEWER[2])
_RIGHT = _normalise(_cross(_FORWARD, (0.0, 0.0, 1.0)))
_UP = _normalise(_cross(_RIGHT, _FORWARD))


@dataclass(frozen=True)
class Face:
    corners: tuple[Vector, ...]
    fill: str


@dataclass(frozen=True)
class Projection:
    """Where a model's origin lands on the page, and how many pixels a model unit is."""

    origin_x: float
    origin_y: float
    scale: float

    def point(self, p: Vector) -> tuple[float, float]:
        return self.origin_x + self.scale * _dot(p, _RIGHT), self.origin_y - self.scale * _dot(p, _UP)

    def paint(self, canvas: Canvas, faces: list[Face], stroke: str = EDGE) -> None:
        """The faces turned towards the viewer, furthest first. A curved surface made of
        many thin faces reads better without an outline on each: pass stroke="none"."""
        for face in sorted((f for f in faces if _faces_viewer(f)), key=_depth):
            self.polygon(canvas, face.corners, face.fill, stroke=stroke)

    def polygon(self, canvas: Canvas, corners: tuple[Vector, ...], fill: str, stroke: str = "none") -> None:
        points = " ".join(f"{x:.1f},{y:.1f}" for x, y in map(self.point, corners))
        canvas.add(f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="1.2" '
                   'stroke-linejoin="round"/>')


def box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float,
        top: str, side: str, end: str) -> list[Face]:
    """The six faces of a box; the two at either end of x get the `end` colour."""
    return [
        Face(((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)), top),
        Face(((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)), side),
        Face(((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)), side),
        Face(((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)), side),
        Face(((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)), end),
        Face(((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)), end),
    ]


def stadium(width: float, height: float, points_per_end: int = 10) -> list[tuple[float, float]]:
    """A rounded slot in the x-z plane, centred on the origin, anticlockwise from +x."""
    radius = height / 2
    straight = width / 2 - radius
    outline = []
    for i in range(points_per_end + 1):
        a = -math.pi / 2 + math.pi * i / points_per_end
        outline.append((straight + radius * math.cos(a), radius * math.sin(a)))
    for i in range(points_per_end + 1):
        a = math.pi / 2 + math.pi * i / points_per_end
        outline.append((-straight + radius * math.cos(a), radius * math.sin(a)))
    return outline


def prism_along_y(outline: list[tuple[float, float]], y_front: float, y_back: float,
                  front: str, side: str) -> list[Face]:
    """An outline in the x-z plane pushed back from y_front to y_back.

    `outline` runs anticlockwise seen from the front (from negative y)."""
    faces = [
        Face(tuple((x, y_front, z) for x, z in outline), front),
        Face(tuple((x, y_back, z) for x, z in reversed(outline)), side),
    ]
    for (xa, za), (xb, zb) in zip(outline, outline[1:] + outline[:1], strict=True):
        faces.append(Face(((xa, y_front, za), (xa, y_back, za), (xb, y_back, zb), (xb, y_front, zb)), side))
    return faces


def _normal(face: Face) -> Vector:
    """Newell's method: robust for polygons with many corners, such as a stadium."""
    nx = ny = nz = 0.0
    corners = face.corners
    for (x0, y0, z0), (x1, y1, z1) in zip(corners, corners[1:] + corners[:1], strict=True):
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return nx, ny, nz


def _faces_viewer(face: Face) -> bool:
    return _dot(_normal(face), TOWARDS_VIEWER) > 1e-9


def _depth(face: Face) -> float:
    n = len(face.corners)
    centre = (sum(c[0] for c in face.corners) / n, sum(c[1] for c in face.corners) / n,
              sum(c[2] for c in face.corners) / n)
    return _dot(centre, TOWARDS_VIEWER)
