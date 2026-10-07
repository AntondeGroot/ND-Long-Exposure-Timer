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
    Region("Region 2: soft latch", LATCH, 18, 24, "F", "GP12", "GP16"),
]

PAD_COLOURS = {"GP22": RING, "GP12": LATCH, "GP16": LATCH} | dict.fromkeys(
    ["GP5", "GP6", "GP13", "GP20", "GP19", "GP26", "GP21"], BUTTON_PAD)

LABEL_ROW_Y = g.ORIGIN_Y + 530  # between the pad names and row A


@dataclass(frozen=True)
class Step:
    title: str
    parts: tuple[Part, ...]


STEPS = [
    Step("Resistors and BAT85s", (
        Resistor("1k", "GP22", "9A", (g.column_x(9) + 30, LABEL_ROW_Y)),
        Resistor("10k", "GP16", "22A", (g.column_x(21) - 4, LABEL_ROW_Y)),
        Resistor("10k", "19C", "21B", (g.column_x(20), g.row_y("B") + 14)),
        Resistor("100k", "20F", "21F", (g.column_x(22) + 14, g.row_y("F") + 6)),
        Diode("GP12", "18A", (g.column_x(17) + 4, LABEL_ROW_Y), "sense"),
        Diode("19B", "18B", ((g.column_x(18) + g.column_x(19)) / 2, g.row_y("B") - 17), "start"),
    )),
    Step("The AO3401 on its adapter", (
        Mosfet("19E", "21E"),
    )),
    # The bridge comes after the transistors: the soft latch's collector goes in 21C, and a
    # blob of solder there first would close the hole.
    Step("The two BC337s and the solder bridge", (
        Transistor("8B", "10B", "ring"),
        Transistor("21C", "23C", "soft latch"),
        SolderBridge("21C", "21D"),
    )),
    Step("The GND jumper and the wires that leave the board", (
        Jumper(("10C", (g.column_x(10) + g.PITCH / 2, g.row_y("C") + 22),
                (g.column_x(10) + g.PITCH / 2, g.ORIGIN_Y + 852), (g.column_x(23), g.ORIGIN_Y + 852), "23D"),
               "the ring transistor's emitter", (g.column_x(14), g.ORIGIN_Y + 842)),
        Wire(1, "1D", "button LED + (5V rail)", LED_WIRE),
        Wire(2, "8A", "button LED -", LED_WIRE),
        Wire(3, "18C", "power button switch, NO", SWITCH_WIRE),
        Wire(6, "24A", "power button switch, COM (GND)", SWITCH_WIRE),
        Wire(4, "19D", "UPS switch MIDDLE pin (boost in), thick wire", POWER_WIRE),
        Wire(5, "20D", "UPS switch ON pin (SYS, battery), thick wire", POWER_WIRE),
    )),
    Step("The button wires", (
        Wire(7, "GP5", "five-way left", BUTTON_WIRE),
        Wire(8, "GP6", "five-way up", BUTTON_WIRE),
        Wire(9, "GP13", "five-way centre", BUTTON_WIRE),
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
    "Adapter assumed G-S-D in a row: check it before soldering.",
]
