"""The things that get soldered on, each able to draw itself and say where it goes.

A part names its holes the way the guide does - "21C" for column 21, row C, or a pad
name such as "GP22" - so the layout reads like the instructions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from . import geometry as g
from .svg import Canvas

LEG = "#9a9a9a"
ADAPTER_LENGTH = 4.5  # holes, legs included
GND_WIRE = "#212529"
# Seen from above a part stood on end is a circle as wide as its body. These are the
# parts in hand: 1/8W resistors, 3.5mm long and 1.8mm across, and BAT85s in DO-35 glass,
# 3.8mm long and about 1.9mm across.
# Stood up, both are about 5mm tall: clear of the e-paper display on the header above, but
# not of its connector, which hangs down to 4mm over columns 9-16 of rows D-F.
RESISTOR_DIAMETER = 1.8 * g.UNITS_PER_MM
DIODE_DIAMETER = 1.9 * g.UNITS_PER_MM
# A part lying flat is drawn slimmer than life: to scale it hides the holes around it,
# and nothing stands next to it for its true width to matter.
LYING_LENGTH, LYING_WIDTH = 50, 16
# Two parts sharing a pair of holes: one part's legs go in the side of each hole facing the
# other hole, the other part's in the far side. This far off the centre they are drawn.
LEG_INSET = 7

Side = Literal["inner", "outer"]


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


def _standing(canvas: Canvas, base: g.Point, top_leg_to: g.Point, diameter: float, fill: str, rim: str) -> None:
    """A part stood on end over `base`, seen from above: its body, and the leg that comes
    out of the top and bends over down into the other hole."""
    canvas.circle(base, diameter / 2, fill, rim, 2)
    canvas.line(base, top_leg_to, LEG, 4)
    canvas.circle(base, 4, LEG)


def _lying(canvas: Canvas, a: g.Point, b: g.Point, fill: str, rim: str, stripe_at_b: str | None = None) -> None:
    """A part lying flat from `a` to `b`, seen from above: its legs and, halfway, its body -
    with a stripe of that colour at the `b` end, for a diode's cathode."""
    canvas.line(a, b, LEG, 4)
    x, y = _midpoint(a, b)
    length, width, stripe = LYING_LENGTH, LYING_WIDTH, LYING_LENGTH / 6
    band = (
        f'<rect x="{length / 2 - 2 * stripe:.1f}" y="{-width / 2:.1f}" width="{stripe:.1f}" '
        f'height="{width}" fill="{stripe_at_b}"/>'
        if stripe_at_b
        else ""
    )
    canvas.add(
        f'<g transform="translate({x:.1f},{y:.1f}) rotate({_angle(a, b):.1f})">'
        f'<rect x="{-length / 2:.1f}" y="{-width / 2:.1f}" width="{length}" height="{width}" '
        f'rx="5" fill="{fill}" stroke="{rim}" stroke-width="2"/>{band}</g>'
    )


def _bent_leg(canvas: Canvas, hole: g.Point, body_end: g.Point, side: Side) -> None:
    """A leg bent at a right angle: straight up out of one side of its hole to the body's
    height, then across into the body's end."""
    towards_body = 1 if body_end[0] > hole[0] else -1
    x = hole[0] + LEG_INSET * (towards_body if side == "inner" else -towards_body)
    canvas.line((x, hole[1]), (x, body_end[1]), LEG, 4)
    canvas.line((x, body_end[1]), body_end, LEG, 4)


def badge(canvas: Canvas, centre: g.Point, number: int, colour: str, radius: float = 15) -> None:
    """A numbered circle; light fills (a white or yellow wire) get dark text and a dark rim."""
    size = 17 if radius >= 15 else 14
    light = _is_light(colour)
    canvas.circle(centre, radius, colour, "#555" if light else "#fff", 3)
    canvas.text(
        _offset(centre, 0, size / 3 + 0.5), str(number), size, "#111" if light else "#fff", anchor="middle", bold=True
    )


def _is_light(colour: str) -> bool:
    red, green, blue = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.299 * red + 0.587 * green + 0.114 * blue > 170


@dataclass(frozen=True)
class Resistor:
    """Stood up (hairpin) over leg_a, so a short span is fine: one leg straight in under the
    body, the other bent over its top. Or lying flat, which needs its legs three holes apart.

    A lying one can have its body moved off the line between its holes with `body_at`, its
    legs bent out to it: to lie over the label strip, clear of the parts in between. With
    `bent_legs` the legs go up at a right angle from that side of their holes, for when
    another part shares them. `how` replaces the legend's "lying flat" when the way it is
    fitted needs saying.
    """

    value: str
    leg_a: str
    leg_b: str
    label_at: g.Point
    lying: bool = False
    body_at: g.Point | None = None
    how: str | None = None
    bent_legs: Side | None = None

    def pads(self) -> set[str]:
        return {leg for leg in (self.leg_a, self.leg_b) if leg in g.PADS}

    def draw(self, canvas: Canvas) -> None:
        a, b = point(self.leg_a), point(self.leg_b)
        if self.body_at:
            x, y = self.body_at
            left, right = (x - LYING_LENGTH / 2, y), (x + LYING_LENGTH / 2, y)
            for hole, end in ((a, left), (b, right)):
                if self.bent_legs:
                    _bent_leg(canvas, hole, end, self.bent_legs)
                else:
                    canvas.line(hole, end, LEG, 4)
            _lying(canvas, left, right, "#e7cfa0", "#7a6440")
        elif self.lying:
            _lying(canvas, a, b, "#e7cfa0", "#7a6440")
        else:
            _standing(canvas, a, b, RESISTOR_DIAMETER, "#e7cfa0", "#7a6440")
        canvas.board_label(self.label_at, self.value)

    def describe(self) -> str:
        how = self.how or ("lying flat" if self.lying else f"standing on {place(self.leg_a)}")
        return f"{self.value} resistor: {place(self.leg_a)} to {place(self.leg_b)}, {how}"


@dataclass(frozen=True)
class Diode:
    """A BAT85, the stripe at its cathode. Stood up (hairpin) over its anode, so the stripe is
    the end on top - or lying flat, which needs its legs three holes apart."""

    anode: str
    cathode: str
    label_at: g.Point
    role: str
    lying: bool = False

    def pads(self) -> set[str]:
        return {leg for leg in (self.anode, self.cathode) if leg in g.PADS}

    def draw(self, canvas: Canvas) -> None:
        a, k = point(self.anode), point(self.cathode)
        if self.lying:
            _lying(canvas, a, k, "#7a3b2e", "#3b1b14", stripe_at_b="#e6e6e6")
        else:
            _standing(canvas, a, k, DIODE_DIAMETER, "#7a3b2e", "#e6e6e6")
        canvas.board_label(self.label_at, "BAT85", 16)

    def describe(self) -> str:
        anode = place(self.anode)
        how = "lying flat" if self.lying else f"standing on {anode}"
        return f"BAT85 ({self.role}): anode {anode}, stripe {place(self.cathode)}, {how}"


@dataclass(frozen=True)
class Capacitor:
    """A ceramic capacitor with both legs out of one end, seen from above: its legs from the
    holes to the body, and the body where it ends up - bent flat, or arched over a hole that
    something else still needs.

    An electrolytic works in the same place if `plus` is set: its long leg, the end without
    the stripe, goes there. `angle` turns the body, in degrees clockwise, so it can lie
    alongside a part that runs askew. `bent_legs` takes each leg up at a right angle from
    that side of its hole into the near end of the body, so it stays apart from another
    part's legs in the same holes.
    """

    value: str
    leg_a: str
    leg_b: str
    role: str
    body_at: g.Point
    body_size: tuple[float, float]
    label_at: g.Point
    how: str
    plus: str | None = None
    angle: float = 0.0
    bent_legs: Side | None = None

    def pads(self) -> set[str]:
        return set()

    def draw(self, canvas: Canvas) -> None:
        width, height = self.body_size
        x, y = self.body_at
        for leg in (self.leg_a, self.leg_b):
            hole = point(leg)
            if self.bent_legs:
                end = (x - width / 2 + 6, y) if hole[0] < x else (x + width / 2 - 6, y)
                _bent_leg(canvas, hole, end, self.bent_legs)
            else:
                canvas.line(hole, self.body_at, LEG, 4)
        # Blue, as the ones in hand are: yellow would vanish against the strips.
        if not self.angle:
            canvas.rect(x - width / 2, y - height / 2, width, height, "#2f7fd6", rx=7, stroke="#0d3d78", stroke_width=2)
        else:
            canvas.add(
                f'<g transform="translate({x:.1f},{y:.1f}) rotate({self.angle:.1f})">'
                f'<rect x="{-width / 2:.1f}" y="{-height / 2:.1f}" width="{width}" height="{height}" '
                f'rx="7" fill="#2f7fd6" stroke="#0d3d78" stroke-width="2"/></g>'
            )
        canvas.board_label(self.label_at, self.value, 16)

    def describe(self) -> str:
        polarity = f"; an electrolytic has its long leg (+) in {self.plus}" if self.plus else ""
        return f"{self.value} capacitor ({self.role}): {self.leg_a} to {self.leg_b}, {self.how}{polarity}"


@dataclass(frozen=True)
class SolderBridge:
    """A blob joining two neighbouring holes of different strips."""

    top: str
    bottom: str
    joins: str = "the gate's two strips"

    def pads(self) -> set[str]:
        return set()

    def draw(self, canvas: Canvas) -> None:
        (x, y0), (_, y1) = point(self.top), point(self.bottom)
        canvas.rect(x - 11, y0, 22, y1 - y0, "#c7c7c7", rx=10, stroke="#7d7d7d", stroke_width=2)

    def describe(self) -> str:
        return f"bridge: {self.top} to {self.bottom} on the underside, joining {self.joins}"


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
        # Flat face towards row F, so the legs read C-B-E left to right as the datasheet draws them.
        half = (x1 - x0) / 2 + 20
        canvas.path(
            f"M {x0 - 20:.1f} {y + 12:.1f} L {x1 + 20:.1f} {y + 12:.1f} L {x1 + 20:.1f} {y:.1f} "
            f"A {half:.1f} 26 0 0 0 {x0 - 20:.1f} {y:.1f} Z",
            "#222",
            opacity=0.88,
        )
        for x, letter in [(x0, "C"), ((x0 + x1) / 2, "B"), (x1, "E")]:
            canvas.circle((x, y), 6, "#bbb")
            canvas.text((x, y + 30), letter, 15, "#fff", anchor="middle", bold=True, halo="#222")
        canvas.text(((x0 + x1) / 2, y - 12), "BC337", 15, "#fff", anchor="middle", bold=True)

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
        """Either way round: the gate can be on the left or the right. The adapter is about
        4.5 holes long and lies flat from its legs down over the three rows below them."""
        (x_source, y), (x_gate, _) = point(self.source), point(self.gate)
        left, right = min(x_source, x_gate), max(x_source, x_gate)
        middle = (left + right) / 2
        top, bottom = y - g.PITCH / 2, y + ADAPTER_LENGTH * g.PITCH - g.PITCH / 2
        canvas.rect(
            left - 24,
            top,
            right - left + 48,
            bottom - top,
            "#2b5d9b",
            rx=4,
            stroke="#0f2e55",
            stroke_width=2,
            opacity=0.92,
        )
        canvas.rect(middle - 16, (y + bottom) / 2 - 22, 32, 22, "#111")
        for x, letter in [(x_source, "S"), (middle, "D"), (x_gate, "G")]:
            canvas.circle((x, y), 6, "#bbb")
            canvas.board_label((x, y - 22), letter, 16)
        canvas.text((middle, (y + bottom) / 2 + 24), "AO3401", 15, "#fff", anchor="middle", bold=True)
        canvas.text((middle, (y + bottom) / 2 + 44), "on adapter", 13, "#fff", anchor="middle", bold=True)

    def describe(self) -> str:
        drain = _middle_hole(self.source, self.gate)
        return f"AO3401 on its adapter, on a 1x3 header: source {self.source}, drain {drain}, gate {self.gate}"


@dataclass(frozen=True)
class Jumper:
    """An insulated wire from hole to hole along the given route; dashed when it runs under the board."""

    route: tuple[str | g.Point, ...]
    purpose: str
    label_at: g.Point | None = None
    label: str = "GND wire (insulated)"
    net: str = "GND"
    colour: str = GND_WIRE
    underneath: bool = False

    def pads(self) -> set[str]:
        return set()

    def draw(self, canvas: Canvas) -> None:
        points = [point(p) if isinstance(p, str) else p for p in self.route]
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
        dashes = {"stroke_dasharray": "14 9"} if self.underneath else {}
        canvas.path(d, stroke=self.colour, stroke_width=7, stroke_linecap="round", stroke_linejoin="round", **dashes)
        if self.label_at:
            canvas.board_label(self.label_at, self.label)

    def describe(self) -> str:
        where = " under the board" if self.underneath else ""
        return f"{self.net} wire{where}: {self.route[0]} to {self.route[-1]}, {self.purpose}"


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


Part = Resistor | Diode | Capacitor | SolderBridge | Transistor | Mosfet | Jumper | Wire
