"""A page of SVG, written one element at a time."""

from __future__ import annotations

from contextlib import contextmanager

from .geometry import Point

FONT = "Helvetica, Arial, sans-serif"
BOARD_GREEN = "#1f6b48"


class Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._elements: list[str] = []

    def add(self, element: str) -> None:
        self._elements.append(element)

    @contextmanager
    def faded(self, opacity: float):
        """Everything drawn inside shows through at this opacity: earlier steps, already done."""
        self.add(f'<g opacity="{opacity}">')
        yield
        self.add("</g>")

    def circle(self, centre: Point, radius: float, fill: str, stroke: str = "none", stroke_width: float = 0) -> None:
        x, y = centre
        self.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{stroke_width}"/>')

    def rect(self, x: float, y: float, width: float, height: float, fill: str, **extra: object) -> None:
        attributes = "".join(f' {name.replace("_", "-")}="{value}"' for name, value in extra.items())
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
                 f'fill="{fill}"{attributes}/>')

    def line(self, start: Point, end: Point, colour: str, width: float) -> None:
        self.add(f'<line x1="{start[0]:.1f}" y1="{start[1]:.1f}" x2="{end[0]:.1f}" y2="{end[1]:.1f}" '
                 f'stroke="{colour}" stroke-width="{width}" stroke-linecap="round"/>')

    def path(self, d: str, fill: str = "none", **extra: object) -> None:
        attributes = "".join(f' {name.replace("_", "-")}="{value}"' for name, value in extra.items())
        self.add(f'<path d="{d}" fill="{fill}"{attributes}/>')

    def text(self, at: Point, content: str, size: float, colour: str = "#111",
             anchor: str = "start", bold: bool = False, halo: str | None = None) -> None:
        """Text, optionally outlined in `halo` so it reads over holes and strips."""
        weight = ' font-weight="bold"' if bold else ""
        outline = f' stroke="{halo}" stroke-width="4" paint-order="stroke"' if halo else ""
        self.add(f'<text x="{at[0]:.1f}" y="{at[1]:.1f}" font-size="{size}" fill="{colour}" '
                 f'text-anchor="{anchor}"{weight}{outline}>{content}</text>')

    def board_label(self, at: Point, content: str, size: float = 17) -> None:
        """White bold text on the board, outlined in board green."""
        self.text(at, content, size, "#fff", anchor="middle", bold=True, halo=BOARD_GREEN)

    def svg(self) -> str:
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" '
                f'width="{self.width}" height="{self.height}" font-family="{FONT}">\n'
                f'<rect width="{self.width}" height="{self.height}" fill="#ffffff"/>')
        return "\n".join([head, *self._elements, "</svg>"]) + "\n"
