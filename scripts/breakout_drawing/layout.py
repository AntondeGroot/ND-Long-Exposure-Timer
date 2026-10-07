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
BUTTON_WIRE = "#0b7285"
LED_WIRE = "#c92a2a"
SWITCH_WIRE = "#6741d9"
POWER_WIRE = "#d6336c"
GROUND_WIRE = "#212529"

REGIONS = [
    Region("Region 1: button ring", RING, 8, 10, "C", "GP22", "GP22"),
    Region("Region 2: soft latch", LATCH, 15, 18, "F", "GP5", "GP6"),
]

PAD_COLOURS = {"GP22": RING, "GP5": LATCH, "GP6": LATCH} | dict.fromkeys(
    ["GP12", "GP13", "GP16", "GP20", "GP19", "GP26", "GP21"], BUTTON_PAD)

LABEL_ROW_Y = g.ORIGIN_Y + 530  # between the pad names and row A


@dataclass(frozen=True)
class Step:
    title: str
    parts: tuple[Part, ...]


BETWEEN_C_AND_D = (g.row_y("C") + g.row_y("D")) / 2
BELOW_ROW_F = g.ORIGIN_Y + 852

# The soft latch keeps its BC337 (row B) three rows clear of the MOSFET adapter (row E),
# which stands up and would otherwise lean into it. Its gate needs two strips, column 16
# top and bottom; the 100k's leg in 16D, bent over onto 16C underneath, joins them.
STEPS = [
    Step("Resistors, diodes and the bridge", (
        Resistor("1k", "GP22", "9A", (g.column_x(9) + 30, LABEL_ROW_Y)),
        Resistor("10k", "GP6", "17A", (g.column_x(18) + 4, LABEL_ROW_Y)),
        Resistor("10k", "16F", "15F", (g.column_x(14) - 6, g.row_y("F") + 6)),
        Resistor("100k", "16D", "18D", (g.column_x(17), g.row_y("D") - 16)),
        Diode("GP5", "15A", (g.column_x(14) + 10, LABEL_ROW_Y), "sense"),
        Diode("15D", "15C", (g.column_x(14), BETWEEN_C_AND_D + 6), "start"),
        SolderBridge("16C", "16D"),
    )),
    Step("The AO3401 on its adapter", (
        Mosfet("18E", "16E"),
    )),
    Step("The two BC337s", (
        Transistor("8B", "10B", "ring"),
        Transistor("16B", "18B", "soft latch"),
    )),
    Step("The GND jumpers and the wires that leave the board", (
        Jumper(("10C", (g.column_x(10) + g.PITCH / 2, g.row_y("C") + 22),
                (g.column_x(10) + g.PITCH / 2, BELOW_ROW_F), (g.column_x(23), BELOW_ROW_F), "23D"),
               "the ring transistor's emitter", (g.column_x(11.5), BELOW_ROW_F - 10)),
        Jumper(("18C", (g.column_x(18) + g.PITCH / 2, BETWEEN_C_AND_D),
                (g.column_x(22) + g.PITCH / 2, BETWEEN_C_AND_D), "23C"),
               "the soft latch transistor's emitter"),
        Wire(1, "1D", "button LED + (5V rail)", LED_WIRE),
        Wire(2, "8A", "button LED -", LED_WIRE),
        Wire(3, "15B", "power button switch, NO", SWITCH_WIRE),
        Wire(6, "24A", "power button switch, COM (GND)", SWITCH_WIRE),
        Wire(4, "17F", "UPS switch MIDDLE pin (boost in), thick wire", POWER_WIRE),
        Wire(5, "18F", "UPS switch ON pin (SYS, battery), thick wire", POWER_WIRE),
    )),
    Step("The button wires", (
        Wire(7, "GP12", "five-way left", BUTTON_WIRE),
        Wire(8, "GP13", "five-way centre", BUTTON_WIRE),
        Wire(9, "GP16", "five-way up", BUTTON_WIRE),
        Wire(10, "GP20", "SYNC", BUTTON_WIRE),
        Wire(11, "GP19", "five-way down", BUTTON_WIRE),
        Wire(12, "GP26", "five-way right", BUTTON_WIRE),
        Wire(13, "GP21", "SHOOT", BUTTON_WIRE),
        Wire(14, "24C", "one wire, daisy-chained to all seven buttons (GND)", GROUND_WIRE),
    )),
]

NOTES = [
    "Resistors and diodes stand up (hairpin); the GPIO ones have one leg in the pad itself. "
    "Diode stripe = cathode.",
    "Transistors: base in the middle, emitter to the right. "
    "MOSFET adapter: legs 2-3-1 are source, drain, gate; leg 1 in 16E.",
]
