"""The things that get soldered on, each able to draw itself and say where it goes.

A part names its holes the way the guide does - "21C" for column 21, row C, or a pad
name such as "GP22" - so the layout reads like the instructions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import geometry as g
from .svg import Canvas

LEG = "#9a9a9a"


def point(name: str) -> g.Point:
    return g.pad(name) if name in g.PADS else g.hole(name)


def place(name: str) -> str:
    """How the legend writes a position."""
    return f"{name} pad" if name in g.PADS else name


def _middle_hole(left: str, right: str) -> str:
    """The hole halfway along a row between two others: where a three-legged part's middle leg goes."""
    middle = (int(left[:-1]) + int(right[:-1])) // 2
    return f"{middle}{left[-1]}"


def _offset(at: g.Point, dx: float, dy: float) -> g.Point:
    return at[0] + dx, at[1] + dy


def _midpoint(a: g.Point, b: g.Point) -> g.Point:
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def _angle(a: g.Point, b: g.Point) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def badge(canvas: Canvas, centre: g.Point, number: int, colour: str, radius: float = 15) -> None:
    """A numbered circle; light fills (a white or yellow wire) get dark text and a dark rim."""
    size = 17 if radius >= 15 else 14
    light = _is_light(colour)
    canvas.circle(centre, radius, colour, "#555" if light else "#fff", 3)
    canvas.text(_offset(centre, 0, size / 3 + 0.5), str(number), size, "#111" if light else "#fff",
                anchor="middle", bold=True)


def _is_light(colour: str) -> bool:
    red, green, blue = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * red + 0.587 * green + 0.114 * blue > 170


@dataclass(frozen=True)
class Resistor:
    """Stood up (hairpin), so a short span is fine: one leg straight in, the other bent over."""

    value: str
    leg_a: str
    leg_b: str
    label_at: g.Point

    def pads(self) -> set[str]:
        return {leg for leg in (self.leg_a, self.leg_b) if leg in g.PADS}

    def draw(self, canvas: Canvas) -> None:
        a, b = point(self.leg_a), point(self.leg_b)
        canvas.line(a, b, LEG, 4)
        x, y = _midpoint(a, b)
        canvas.add(f'<g transform="translate({x:.1f},{y:.1f}) rotate({_angle(a, b):.1f})">'
                   '<rect x="-21" y="-9" width="42" height="18" rx="8" fill="#e7cfa0" '
                   'stroke="#7a6440" stroke-width="2"/></g>')
        canvas.board_label(self.label_at, self.value)

    def describe(self) -> str:
        return f"{self.value} resistor: {place(self.leg_a)} to {place(self.leg_b)}"


@dataclass(frozen=True)
class Diode:
    """A BAT85: the stripe is the cathode."""

    anode: str
    cathode: str
    label_at: g.Point
    role: str

    def pads(self) -> set[str]:
        return {leg for leg in (self.anode, self.cathode) if leg in g.PADS}

    def draw(self, canvas: Canvas) -> None:
        a, k = point(self.anode), point(self.cathode)
        canvas.line(a, k, LEG, 4)
        x, y = _midpoint(a, k)
        canvas.add(f'<g transform="translate({x:.1f},{y:.1f}) rotate({_angle(a, k):.1f})">'
                   '<rect x="-17" y="-8" width="34" height="16" rx="5" fill="#7a3b2e" '
                   'stroke="#3b1b14" stroke-width="2"/>'
                   '<rect x="7" y="-8" width="6" height="16" fill="#e6e6e6"/></g>')
        canvas.board_label(self.label_at, "BAT85", 16)

    def describe(self) -> str:
        return f"BAT85 ({self.role}): anode {place(self.anode)}, stripe {place(self.cathode)}"


@dataclass(frozen=True)
class SolderBridge:
    """A blob joining two neighbouring holes of different strips."""

    top: str
    bottom: str

    def pads(self) -> set[str]:
        return set()

    def draw(self, canvas: Canvas) -> None:
        (x, y0), (_, y1) = point(self.top), point(self.bottom)
        canvas.rect(x - 11, y0, 22, y1 - y0, "#c7c7c7", rx=10, stroke="#7d7d7d", stroke_width=2)

    def describe(self) -> str:
        return f"bridge: {self.top} to {self.bottom} on the underside, joining the gate's two strips"


@dataclass(frozen=True)
class Transistor:
    """A BC337 in TO-92: collector left, base in the middle, emitter right."""

    collector: str
    emitter: str
    job: str

    def pads(self) -> set[str]:
        return set()

    def draw(self, canvas: Canvas) -> None:
        (x0, y), (x1, _) = point(self.collector), point(self.emitter)
        half = (x1 - x0) / 2 + 20
        canvas.path(f"M {x0 - 20:.1f} {y - 12:.1f} L {x1 + 20:.1f} {y - 12:.1f} L {x1 + 20:.1f} {y:.1f} "
                    f"A {half:.1f} 26 0 0 1 {x0 - 20:.1f} {y:.1f} Z", "#222", opacity=0.88)
        for x, letter in [(x0, "C"), ((x0 + x1) / 2, "B"), (x1, "E")]:
            canvas.circle((x, y), 6, "#bbb")
            canvas.text((x, y + 30), letter, 15, "#fff", anchor="middle", bold=True)
        canvas.text(((x0 + x1) / 2, y - 20), "BC337", 17, "#fff", anchor="middle", bold=True, halo="#222")

    def describe(self) -> str:
        base = _middle_hole(self.collector, self.emitter)
        return f"BC337 ({self.job}): collector {self.collector}, base {base}, emitter {self.emitter}"


@dataclass(frozen=True)
class Mosfet:
    """The AO3401 on its SOT-23 to SIP3 adapter. The adapter's legs run 2-3-1, which for
    the AO3401 is source, drain, gate: the drain is the middle leg."""

    source: str
    gate: str

    def pads(self) -> set[str]:
        return set()

    def draw(self, canvas: Canvas) -> None:
        """Either way round: the gate can be on the left or the right."""
        (x_source, y), (x_gate, _) = point(self.source), point(self.gate)
        left, right = min(x_source, x_gate), max(x_source, x_gate)
        middle = (left + right) / 2
        canvas.rect(left - 24, y - 16, right - left + 48, 42, "#2b5d9b", rx=4, stroke="#0f2e55", stroke_width=2)
        canvas.rect(middle - 12, y - 8, 24, 16, "#111")
        for x, letter in [(x_source, "S"), (middle, "D"), (x_gate, "G")]:
            canvas.circle((x, y), 6, "#bbb")
            canvas.board_label((x, y - 22), letter, 16)
        canvas.text((middle, y + 22), "AO3401 on adapter", 13, "#fff", anchor="middle", bold=True)

    def describe(self) -> str:
        drain = _middle_hole(self.source, self.gate)
        return f"AO3401 on its adapter: source {self.source}, drain {drain}, gate {self.gate}"


@dataclass(frozen=True)
class Jumper:
    """An insulated wire on the board, along the given route."""

    route: tuple[str | g.Point, ...]
    purpose: str
    label_at: g.Point | None = None

    def pads(self) -> set[str]:
        return set()

    def draw(self, canvas: Canvas) -> None:
        points = [point(p) if isinstance(p, str) else p for p in self.route]
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
        canvas.path(d, stroke="#2f9e44", stroke_width=7, stroke_linecap="round", stroke_linejoin="round")
        if self.label_at:
            canvas.board_label(self.label_at, "GND jumper (insulated)")

    def describe(self) -> str:
        return f"GND jumper: {self.route[0]} to {self.route[-1]}, {self.purpose}"


@dataclass(frozen=True)
class Wire:
    """A wire that leaves the board, marked by a numbered badge on the hole it goes into."""

    number: int
    at: str
    to: str
    colour: str
    colour_name: str = ""

    def pads(self) -> set[str]:
        return {self.at} if self.at in g.PADS else set()

    def draw(self, canvas: Canvas) -> None:
        radius = 14 if self.at in g.PADS else 15
        badge(canvas, point(self.at), self.number, self.colour, radius)

    def describe(self) -> str:
        wire = f" ({self.colour_name})" if self.colour_name else ""
        return f"{place(self.at)}  ->  {self.to}{wire}"


Part = Resistor | Diode | SolderBridge | Transistor | Mosfet | Jumper | Wire
