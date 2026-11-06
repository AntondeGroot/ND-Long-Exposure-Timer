"""The finished board's two meter checks: the diodes with the power off, then the voltages.

The expected values are worked out from the circuit in docs/power-button.md, not measured.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import geometry as g
from .board import draw_board
from .layout import STEPS
from .parts import Diode, Part
from .svg import Canvas

WIDTH = 1510
TABLE_TOP = 880
ROW_HEIGHT = 46
MARKER_RADIUS = 24
DONE_OPACITY = 0.3
RED_PROBE = "#c92a2a"
BLACK_PROBE = "#111"
ZEBRA = "#f1f3f5"
NOTE = "#444"
SUBTITLE = "Top view, header at the top. Probe the solder joint where a hole is already filled."


@dataclass(frozen=True)
class DiodeCheck:
    name: str
    red: str  # where the red probe goes, by the name the guide uses
    black: str

    @property
    def number(self) -> str:
        return self.name[0]


DIODE_CHECKS = [
    DiodeCheck("1 Start diode", "12E", "13C"),
    DiodeCheck("2 Sense diode", "GP5", "13A"),
]


@dataclass(frozen=True)
class VoltagePoint:
    tag: str
    at: str
    what: str
    off: str
    held: str
    running: str
    pressed: str


CELL = "cell"
VOLTAGE_POINTS = [
    VoltagePoint("T1", "21A", "SYS, the cell (wire 5)", CELL, CELL, CELL, CELL),
    VoltagePoint("T2", "20A", "MOSFET drain (wire 4)", "0", CELL, CELL, CELL),
    VoltagePoint("T3", "19A", "MOSFET gate", CELL, "under 0.7", "under 0.2", "under 0.2"),
    VoltagePoint("T4", "13A", "Button side of the diodes", "near cell", "0", "about 3", "0"),
    VoltagePoint("T5", "GP5", "Sense line", "about 0", "0.2-0.4", "3.3", "0.2-0.4"),
    VoltagePoint("T6", "GP6", "Hold line", "0", "3.3", "3.3", "3.3"),
    VoltagePoint("T7", "1A", "5V rail", "0", "about 5", "about 5", "about 5"),
    VoltagePoint("T8", "2A", "3.3V rail", "0", "3.3", "3.3", "3.3"),
    VoltagePoint("T9", "GP22", "Ring line", "0", "3.3", "0 *", "0 *"),
]
BLACK_PROBE_HOLE = "24D"

COLUMN_TITLES = ["1. Off", "2. Held from off", "3. Running", "4. Pressed"]
COLUMN_XS = [640, 860, 1080, 1300]
VOLTAGE_NOTES = [
    "All values in volts. cell = what T1 reads, 3.0-4.2V. Slide switch on OFF, charger out, display off the board.",
    "1. Off: nothing touched.",
    "2. Held from off: hold the button and read within 5 seconds. T6 reads about 1.1 for the first second.",
    "3. Running: button released, about 30 seconds after the start.",
    "4. Pressed: a press starts a clean shutdown, so read one point per press. Afterwards column 1 applies again.",
    "* T9 stays at 3.3 until the app has drawn its first screen, so without the display it may never drop.",
    "T2 off can read a few volts on a 10MΩ meter: MOSFET leakage with nothing to load it. "
    "A 10k from 20A to GND makes it 0.",
]


DIODE_NOTES = [
    "Take the cell out and unplug the charger. Set the meter to its diode range and leave the button alone.",
    "Go by these holes, not by the stripes: the readings prove which way round each diode is soldered.",
]


def diode_check_page() -> str:
    canvas = Canvas(WIDTH, TABLE_TOP + 260)
    _draw_title(canvas, "Check 1: the two diodes, with the power off")
    _draw_faded_board(canvas, highlighted=[p for step in STEPS for p in step.parts if isinstance(p, Diode)])
    for check in DIODE_CHECKS:
        _marker(canvas, check.red, f"{check.number}+", RED_PROBE, "#fff", RED_PROBE)
        _marker(canvas, check.black, f"{check.number}\N{MINUS SIGN}", BLACK_PROBE, BLACK_PROBE, "#fff")
    _draw_diode_table(canvas)
    return canvas.svg()


def voltage_check_page() -> str:
    top_of_notes = TABLE_TOP + 70 + len(VOLTAGE_POINTS) * ROW_HEIGHT + 30
    canvas = Canvas(WIDTH, top_of_notes + len(VOLTAGE_NOTES) * 30 + 20)
    _draw_title(canvas, "Check 2: the voltages, in four states")
    _draw_faded_board(canvas)
    for point in VOLTAGE_POINTS:
        _marker(canvas, point.at, point.tag, RED_PROBE, "#fff", RED_PROBE)
    _marker(canvas, BLACK_PROBE_HOLE, "GND", BLACK_PROBE, BLACK_PROBE, "#fff", size=15)
    _draw_voltage_table(canvas)
    _draw_notes(canvas, top_of_notes)
    return canvas.svg()


def _draw_title(canvas: Canvas, title: str) -> None:
    canvas.text((40, 60), title, 34, bold=True)
    canvas.text((40, 100), SUBTITLE, 21, NOTE)


def _draw_faded_board(canvas: Canvas, highlighted: list[Part] | None = None) -> None:
    highlighted = highlighted or []
    draw_board(canvas, {})
    with canvas.faded(DONE_OPACITY):
        for step in STEPS:
            for part in step.parts:
                if part not in highlighted:
                    part.draw(canvas)
    for part in highlighted:
        part.draw(canvas)


def _marker(canvas: Canvas, at: str, label: str, ring: str, fill: str, text_colour: str, size: float = 19) -> None:
    centre = g.pad(at) if at in g.PADS else g.hole(at)
    canvas.circle(centre, MARKER_RADIUS, fill, ring, 5)
    canvas.text((centre[0], centre[1] + size * 0.36), label, size, text_colour, anchor="middle", bold=True)


def _draw_diode_table(canvas: Canvas) -> None:
    columns = [80, 400, 620, 840, 1130]
    titles = ["Diode", "Red probe", "Black probe", "Reading", "Probes swapped"]
    for x, title in zip(columns, titles, strict=True):
        canvas.text((x, TABLE_TOP), title, 22, bold=True)
    for i, check in enumerate(DIODE_CHECKS):
        y = TABLE_TOP + 46 + i * ROW_HEIGHT
        cells = [check.name, check.red, check.black, "0.2-0.4V", "OL"]
        for x, cell in zip(columns, cells, strict=True):
            canvas.text((x, y), cell, 21, "#222")
    notes_top = TABLE_TOP + 46 + len(DIODE_CHECKS) * ROW_HEIGHT + 20
    for i, note in enumerate(DIODE_NOTES):
        canvas.text((80, notes_top + i * 32), note, 21, NOTE)


def _draw_voltage_table(canvas: Canvas) -> None:
    canvas.text((80, TABLE_TOP), "Black probe on GND (24D). Red probe on each point:", 22, bold=True)
    header_y = TABLE_TOP + 44
    for x, title in zip(COLUMN_XS, COLUMN_TITLES, strict=True):
        canvas.text((x, header_y), title, 21, anchor="middle", bold=True)
    for i, point in enumerate(VOLTAGE_POINTS):
        _draw_voltage_row(canvas, point, header_y + 16 + i * ROW_HEIGHT, shaded=i % 2 == 0)


def _draw_voltage_row(canvas: Canvas, point: VoltagePoint, top: float, shaded: bool) -> None:
    if shaded:
        canvas.rect(70, top, WIDTH - 140, ROW_HEIGHT, ZEBRA)
    baseline = top + 31
    canvas.text((84, baseline), point.tag, 21, RED_PROBE, bold=True)
    canvas.text((140, baseline), f"{point.at}: {point.what}", 21, "#222")
    values = [point.off, point.held, point.running, point.pressed]
    for x, value in zip(COLUMN_XS, values, strict=True):
        canvas.text((x, baseline), value, 21, "#222", anchor="middle")


def _draw_notes(canvas: Canvas, top: float) -> None:
    for i, note in enumerate(VOLTAGE_NOTES):
        canvas.text((80, top + i * 30), note, 19, NOTE)
