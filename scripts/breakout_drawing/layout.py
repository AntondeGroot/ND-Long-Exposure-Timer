"""The build: every part, the hole it goes in, and the step it is soldered in.

This is the one place to change the layout. Low parts go on first so the board still
lies flat for the next ones; the wires come last, when nothing else needs the iron
near them.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import geometry as g
from .board import Region
from .parts import Diode, Jumper, Mosfet, Part, Resistor, SolderBridge, Transistor, Wire

RING = "#e8590c"
LATCH = "#0b3a8c"
BUTTON_PAD = "#99e9f2"
LED_WIRE = "#c92a2a"
LED_GROUND_WIRE = "#212529"
SWITCH_WIRE = "#6741d9"
POWER_WIRE = "#d6336c"

REGIONS = [
    Region("Region 1: button ring", RING, 3, 9, "C", "GP22", "GP22"),
    Region("Region 2: soft latch", LATCH, 13, 21, "F", "GP5", "GP6"),
]

PAD_COLOURS = {"GP22": RING, "GP5": LATCH, "GP6": LATCH} | dict.fromkeys(
    ["GP12", "GP13", "GP16", "GP20", "GP19", "GP26", "GP21"], BUTTON_PAD
)

LABEL_ROW_Y = g.ORIGIN_Y + 530  # between the pad names and row A


@dataclass(frozen=True)
class CableWire:
    """One wire of the JST cable: its colour, the hole on the board, and the button it reaches."""

    name: str
    colour: str
    at: str
    button: str


# The JST cable, pin 1 first, in the order its wires leave the connector. Purple takes the
# leftmost button pad and red the rightmost, so the cable runs straight along the row.
# The first five follow the five-way's own pins (up, down, left, right, centre), so they
# reach it without crossing; white and red go to SYNC and SHOOT. Black is ground: it goes
# to SYNC and SHOOT, and from there a short wire carries it on to the five-way's ground pin.
JST_CABLE = [
    CableWire("purple", "#7048e8", "GP12", "five-way up"),
    CableWire("blue", "#1c7ed6", "GP13", "five-way down"),
    CableWire("green", "#0ca678", "GP16", "five-way left"),
    CableWire("orange", "#f76707", "GP20", "five-way right"),
    CableWire("yellow", "#fcc419", "GP19", "five-way centre"),
    CableWire("white", "#f8f9fa", "GP26", "SYNC"),
    CableWire("red", "#e03131", "GP21", "SHOOT"),
    CableWire("black", "#212529", "24A", "GND: SYNC, SHOOT, five-way"),
]
FIRST_BUTTON_WIRE = 7


@dataclass(frozen=True)
class Step:
    title: str
    parts: tuple[Part, ...]


BETWEEN_C_AND_D = (g.row_y("C") + g.row_y("D")) / 2
BETWEEN_E_AND_F = (g.row_y("E") + g.row_y("F")) / 2
BELOW_ROW_F = g.ORIGIN_Y + 852

# The MOSFET adapter is about 4.5 holes long: its legs go in row C and it lies flat over
# rows D-F of its columns, so nothing else goes there - only wires under the board pass.
# It sits right of the rest of the soft latch, which keeps to columns 13-16, two columns
# clear of the adapter and the 100k. The gate is column 14, top and bottom, joined by a
# bridge, and a wire under the board takes it on to the gate leg in 19C.
GATE_WIRE = "#f76707"
STEPS = [
    Step(
        "Resistors, diodes and the bridge",
        (
            # Flat: GP22 to the ring transistor's base strip is about 13mm, too long a leg to
            # bend over the top. The leg at the GP22 end passes close to the GP27 pad, so it
            # gets a sleeve of heat-shrink.
            Resistor("1k", "GP22", "4A", (g.column_x(6.5), LABEL_ROW_Y), lying=True),
            # Flat, like the 1k: from the GP6 and GP5 pads to their strips is 9mm and 11mm.
            Resistor("10k", "GP6", "15A", (g.column_x(16.6), LABEL_ROW_Y), lying=True),
            Resistor("10k", "14F", "13F", (g.column_x(12) - 6, g.row_y("F") + 6)),
            # Flat over column 20: two holes apart is just enough for a 3.5mm body.
            Resistor("100k", "19B", "21B", (g.column_x(20), g.row_y("B") - 16), lying=True),
            Diode("GP5", "13A", (g.column_x(13.6), LABEL_ROW_Y), "sense", lying=True),
            # Flat along column 13 over 13D, its legs bent right at the body. That leaves 13B
            # free on top for the switch wire.
            Diode("13E", "13C", (g.column_x(11.7), BETWEEN_C_AND_D + 6), "start", lying=True),
            SolderBridge("14C", "14D"),
        ),
    ),
    Step("The AO3401 on its adapter", (Mosfet("21C", "19C"),)),
    Step(
        "The two BC337s",
        (
            Transistor("3B", "5B", "ring"),
            Transistor("14B", "16B", "soft latch"),
        ),
    ),
    Step(
        "The wires under the board, and the wires that leave it",
        (
            Jumper(
                (
                    "5C",
                    (g.column_x(5) + g.PITCH / 2, g.row_y("C") + 22),
                    (g.column_x(5) + g.PITCH / 2, BELOW_ROW_F),
                    (g.column_x(23), BELOW_ROW_F),
                    "23D",
                ),
                "the ring transistor's emitter",
                (g.column_x(8.5), BELOW_ROW_F - 10),
                label="GND wires (under the board)",
                underneath=True,
            ),
            Jumper(
                (
                    "16C",
                    (g.column_x(16) + g.PITCH / 2, BETWEEN_C_AND_D),
                    (g.column_x(22) + g.PITCH / 2, BETWEEN_C_AND_D),
                    "23C",
                ),
                "the soft latch transistor's emitter",
                underneath=True,
            ),
            Jumper(
                ("14E", (g.column_x(18.5), g.row_y("E")), (g.column_x(18.5), g.row_y("A")), "19A"),
                "the gate on to the MOSFET's gate leg",
                net="Gate",
                colour=GATE_WIRE,
                underneath=True,
            ),
            Jumper(
                (
                    "13B",
                    (g.column_x(12) + g.PITCH / 2, g.row_y("B")),
                    (g.column_x(12) + g.PITCH / 2, BETWEEN_E_AND_F),
                    (g.column_x(3), BETWEEN_E_AND_F),
                    "3F",
                ),
                "the power button's NO strip on to 3D",
                net="Switch",
                colour=SWITCH_WIRE,
                underneath=True,
            ),
            # The power button's wires all leave from the left edge, next to each other, so
            # they run straight off the board and clear of the parts when it is fitted.
            Wire(1, "1C", "button LED + (5V rail)", LED_WIRE),
            Wire(2, "3C", "button LED -", LED_GROUND_WIRE, "black"),
            Wire(3, "3D", "power button switch, NO", SWITCH_WIRE),
            Wire(6, "24C", "power button switch, COM (GND)", SWITCH_WIRE),
            Wire(4, "20A", "UPS switch MIDDLE pin (boost in)", POWER_WIRE),
            Wire(5, "21A", "UPS switch ON pin (SYS, battery)", POWER_WIRE),
        ),
    ),
    Step(
        "The button wires: one half of the JST cable",
        tuple(
            Wire(number, wire.at, wire.button, wire.colour, wire.name)
            for number, wire in enumerate(JST_CABLE, start=FIRST_BUTTON_WIRE)
        ),
    ),
]

NOTES = [
    "Every resistor and diode lies flat except the 10k from 14F to 13F, which stands up (hairpin). "
    "Diode stripe = cathode.",
    "Transistors: flat face towards row F, so C-B-E reads left to right. "
    "MOSFET adapter: legs 2-3-1 are source, drain, gate; leg 1 in 19C. It lies flat over rows D-F.",
]
