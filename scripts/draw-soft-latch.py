#!/usr/bin/env python3
"""Draw the soft latch schematic to docs/soft-latch-circuit.svg.

The circuit lives here, so a change to it is a change to this file followed by a rerun -
never an edit to the SVG. The board layout that builds it is scripts/breakout_drawing/.

Run after changing it:  ./scripts/draw-soft-latch.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import schemdraw
import schemdraw.elements as elm

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "docs" / "soft-latch-circuit.svg"

Point = tuple[float, float]


def drawing() -> schemdraw.Drawing:
    schemdraw.config(fontsize=13, font="sans")
    d = schemdraw.Drawing(show=False)
    gate, gate_to_fet = _power_path(d)
    _hold(d, gate_to_fet)
    _button(d, gate)
    return d


# The gate node sits this far below the SYS rail, and the BC337 this far right of it.
GATE_DROP = 3.0
SOURCE_X, FET_X, HOLD_X = 3.0, 4.0, 6.5


def _power_path(d: schemdraw.Drawing) -> tuple[Point, Point]:
    """SYS through the MOSFET to the boost converter, the gate held up by 100k and 100nF.

    Answers the gate node, and the joint under the MOSFET where the BC337 takes the gate.
    """
    d += elm.Dot(open=True).at((0, 0)).label("UPS switch ON pin\n(SYS, battery)", loc="left")
    d += elm.Line().to((FET_X, 0))
    d += elm.Dot().at((SOURCE_X, 0))
    d += elm.Dot().at((SOURCE_X - 1.2, 0))
    # Turned so the source is on the left, the drain on the right and the gate below.
    d += (fet := elm.PFet(bulk=False).theta(-90).flip().at((FET_X, 0)).anchor("source"))
    d += elm.Label().at((fet.gate[0], 0.9)).label("AO3401 (P-FET)")
    for letter, (x, y) in (("S", fet.source), ("D", fet.drain), ("G", fet.gate)):
        d += (
            elm.Label()
            .at((x + (0.2 if letter == "G" else 0), y + (0.15 if letter == "G" else 0.3)))
            .label(letter, color="#666", fontsize=11)
        )
    d += elm.Line().at(fet.drain).right(1.5)
    d += elm.Dot(open=True).label("UPS switch middle pin\n(boost converter input)", loc="right")

    gate = (SOURCE_X, -GATE_DROP)
    d += elm.Resistor().at((SOURCE_X, 0)).to(gate).label("100kΩ", loc="bottom")
    d += elm.Capacitor().at((SOURCE_X - 1.2, 0)).to((SOURCE_X - 1.2, -GATE_DROP)).label("100nF", loc="top")
    d += elm.Line().to(gate)
    d += elm.Dot().at(gate)
    gate_to_fet = (fet.gate[0], -GATE_DROP)
    d += elm.Line().at(gate).to(gate_to_fet)
    d += elm.Dot()
    d += elm.Line().to(fet.gate)
    return gate, gate_to_fet


def _hold(d: schemdraw.Drawing, gate_to_fet: Point) -> None:
    """The BC337 that holds the gate low while GPIO6 is high, slowed by 10µF on its base."""
    collector = (HOLD_X, gate_to_fet[1])
    d += elm.Line().at(gate_to_fet).to(collector)
    d += (bjt := elm.BjtNpn(circle=True).reverse().at(collector).anchor("collector").label("BC337", loc="left"))
    d += elm.Ground().at(bjt.emitter)
    d += elm.Line().at(bjt.base).right(0.6)
    d += (base := elm.Dot())
    d += elm.Resistor().right().label("10kΩ", loc="top")
    d += elm.Dot(open=True).label("hold GPIO6\n(gpio=6=op,dh,\ngpio-poweroff)", loc="right")
    d += elm.Capacitor().at(base.center).down(2.0).label("10µF", loc="bottom")
    d += elm.Ground()


def _button(d: schemdraw.Drawing, gate: Point) -> None:
    """The press: through the start diode to the gate, and through the sense diode to GPIO5."""
    d += elm.Resistor().at(gate).down().label("10kΩ", loc="bottom")
    d += elm.Schottky().down().label("BAT85", loc="bottom").label("start", loc="top", color="#666")
    d += (button_side := elm.Dot())
    d += elm.Button().down().label("power button\n(momentary, COM-NO)", loc="bottom")
    d += elm.Ground()
    d += elm.Schottky().at(button_side.center).left().reverse().label("BAT85", loc="bottom")
    d += elm.Label().at((button_side.center[0] - 1.5, button_side.center[1] + 0.6)).label("sense", color="#666")
    d += elm.Line().left(0.6)
    d += elm.Dot(open=True).label("sense GPIO5\n(gpio-shutdown)", loc="left")


def svg() -> str:
    return drawing().get_imagedata("svg").decode()


def main() -> int:
    OUTPUT.write_text(svg())
    print(f"wrote {OUTPUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
