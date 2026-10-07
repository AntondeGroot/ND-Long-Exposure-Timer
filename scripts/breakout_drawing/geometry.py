"""Where things are on the board, in drawing units.

The numbers come from AB Electronics' mechanical drawing of the Breakout Pi Zero, at
21.45 units per millimetre, shifted so the board sits a margin in from the page edge.
"""

from __future__ import annotations

ORIGIN_X, ORIGIN_Y = -150, -90
PITCH = 54.8  # 0.1 inch

BOARD_X, BOARD_Y, BOARD_WIDTH, BOARD_HEIGHT = 48, 142, 1394, 644
MOUNTING_HOLES = [(120, 210), (1372, 210), (120, 716), (1372, 716)]

HEADER_X, HEADER_ROW_YS = 225, (192, 247)
HEADER_COLUMNS = 20

PAD_Y = ORIGIN_Y + 410
PADS = ["SCL", "SDA", "TX", "RX", "GP4", "GP17", "GP18", "GP27", "GP22", "GP23",
        "MOSI", "MISO", "SCLK", "CE0", "CE1", "GP25", "GP5", "GP6", "GP12", "GP13",
        "GP16", "GP20", "GP19", "GP26", "GP21"]

ROWS = "ABCDEF"
RAIL_ROWS = "ABCD"
COLUMNS = range(1, 25)
FIVE_VOLT, THREE_VOLT = 1, 2
GROUND = (23, 24)
STRIP_COLUMNS = range(3, 23)

Point = tuple[float, float]


def column_x(column: int) -> float:
    """Grid column 1 is the 5V rail, 24 the right-hand GND column."""
    return ORIGIN_X + 265 + PITCH * (column - 1)


def row_y(row: str) -> float:
    return ORIGIN_Y + 550 + PITCH * ROWS.index(row)


def hole(name: str) -> Point:
    """A grid hole by column and row, as the guide writes it: "21C"."""
    return column_x(int(name[:-1])), row_y(name[-1])


def pad(name: str) -> Point:
    """A GPIO pad, which sits half a pitch off the grid below it."""
    return ORIGIN_X + 240 + PITCH * PADS.index(name), PAD_Y


def rows_of(column: int) -> str:
    """The rails stop at row D; the strips run the full six rows."""
    return ROWS if column in STRIP_COLUMNS else RAIL_ROWS
