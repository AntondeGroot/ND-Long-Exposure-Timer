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
    Region("Region 1: button ring", RING, 8, 10, "C", "GP22", "GP22"),
    Region("Region 2: soft latch", LATCH, 15, 21, "F", "GP5", "GP6"),
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
BELOW_ROW_F = g.ORIGIN_Y + 852

# The MOSFET adapter is about 4.5 holes long: its legs go in row C and it lies flat over
# rows D-F of its columns, so nothing else goes there - only wires under the board pass.
# It sits right of the rest of the soft latch, which keeps the parts that reach up to the
# GP5 and GP6 pads in columns 15-18. The gate is column 16, top and bottom, joined by a
# bridge, and a wire under the board takes it on to the gate leg in 19C.
GATE_WIRE = "#f76707"
STEPS = [
    Step(
        "Resistors, diodes and the bridge",
        (
            Resistor("1k", "GP22", "9A", (g.column_x(9) + 30, LABEL_ROW_Y)),
            Resistor("10k", "GP6", "17A", (g.column_x(18) + 4, LABEL_ROW_Y)),
            Resistor("10k", "16F", "15F", (g.column_x(14) - 6, g.row_y("F") + 6)),
            Resistor("100k", "19B", "21B", (g.column_x(20), g.row_y("B") - 16)),
            Diode("GP5", "15A", (g.column_x(14) + 10, LABEL_ROW_Y), "sense"),
            Diode("15D", "15C", (g.column_x(14), BETWEEN_C_AND_D + 6), "start"),
            SolderBridge("16C", "16D"),
        ),
    ),
    Step("The AO3401 on its adapter", (Mosfet("21C", "19C"),)),
    Step(
        "The two BC337s",
        (
            Transistor("8B", "10B", "ring"),
            Transistor("16B", "18B", "soft latch"),
        ),
    ),
    Step(
        "The wires under the board, and the wires that leave it",
        (
            Jumper(
                (
                    "10C",
                    (g.column_x(10) + g.PITCH / 2, g.row_y("C") + 22),
                    (g.column_x(10) + g.PITCH / 2, BELOW_ROW_F),
                    (g.column_x(23), BELOW_ROW_F),
                    "23D",
                ),
                "the ring transistor's emitter",
                (g.column_x(11.2), BELOW_ROW_F - 10),
                label="GND wires (under the board)",
                underneath=True,
            ),
            Jumper(
                (
                    "18C",
                    (g.column_x(18) + g.PITCH / 2, BETWEEN_C_AND_D),
                    (g.column_x(22) + g.PITCH / 2, BETWEEN_C_AND_D),
                    "23C",
                ),
                "the soft latch transistor's emitter",
                underneath=True,
            ),
            Jumper(
                ("16E", (g.column_x(18.5), g.row_y("E")), (g.column_x(18.5), g.row_y("A")), "19A"),
                "the gate on to the MOSFET's gate leg",
                net="Gate",
                colour=GATE_WIRE,
                underneath=True,
            ),
            Wire(1, "1C", "button LED + (5V rail)", LED_WIRE),
            Wire(2, "8C", "button LED -", LED_GROUND_WIRE, "black"),
            Wire(3, "15B", "power button switch, NO", SWITCH_WIRE),
            Wire(6, "24C", "power button switch, COM (GND)", SWITCH_WIRE),
            Wire(4, "20A", "UPS switch MIDDLE pin (boost in), thick wire", POWER_WIRE),
            Wire(5, "21A", "UPS switch ON pin (SYS, battery), thick wire", POWER_WIRE),
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
    "Resistors and diodes stand up (hairpin); the GPIO ones have one leg in the pad itself. Diode stripe = cathode.",
    "Transistors: flat face towards row F, so C-B-E reads left to right. "
    "MOSFET adapter: legs 2-3-1 are source, drain, gate; leg 1 in 19C. It lies flat over rows D-F.",
]
