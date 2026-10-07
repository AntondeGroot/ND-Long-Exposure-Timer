"""The bare board: header, GPIO pads, rails, strips, and the outlines of the two regions."""

from __future__ import annotations

from dataclasses import dataclass

from . import geometry as g
from .svg import BOARD_GREEN, Canvas

COPPER = "#d9b04a"
HEADER_COPPER = "#c9a23a"
SILKSCREEN = "#e9f3ee"
DRILL = "#1b1b1b"
GRID_NOTE = "#555"


@dataclass(frozen=True)
class Region:
    """A dashed outline: strips first_column..last_column down to last_row, and a narrower
    top reaching up around the GPIO pads the region uses."""

    title: str
    colour: str
    first_column: int
    last_column: int
    last_row: str
    first_pad: str
    last_pad: str


def draw_board(canvas: Canvas, highlighted_pads: dict[str, str]) -> None:
    _draw_outline(canvas)
    _draw_header(canvas)
    _draw_pads(canvas, highlighted_pads)
    _draw_rails_and_strips(canvas)
    _draw_holes(canvas)
    _draw_grid_names(canvas)


def draw_region(canvas: Canvas, region: Region) -> None:
    x0, x1 = g.column_x(region.first_column) - 36, g.column_x(region.last_column) + 36
    top_x0, top_x1 = g.pad(region.first_pad)[0] - 27, g.pad(region.last_pad)[0] + 27
    y0, y_step, y1 = g.PAD_Y - 26, g.row_y("A") - 36, g.row_y(region.last_row) + 36
    canvas.path(f"M {top_x0:.1f} {y0} H {top_x1:.1f} V {y_step:.1f} H {x1:.1f} V {y1:.1f} "
                f"H {x0:.1f} V {y_step:.1f} H {top_x0:.1f} Z",
                stroke=region.colour, stroke_width=4, stroke_dasharray="14 8", stroke_linejoin="round")
    middle = (g.column_x(region.first_column) + g.column_x(region.last_column)) / 2
    canvas.text((middle, g.ORIGIN_Y + 955), region.title, 24, region.colour, anchor="middle", bold=True)


def _draw_outline(canvas: Canvas) -> None:
    canvas.rect(g.BOARD_X, g.BOARD_Y, g.BOARD_WIDTH, g.BOARD_HEIGHT, BOARD_GREEN, rx=55)
    for centre in g.MOUNTING_HOLES:
        canvas.circle(centre, 27, "#ffffff", "#cfcfcf", 2)


def _draw_header(canvas: Canvas) -> None:
    canvas.rect(g.HEADER_X - 27, g.HEADER_ROW_YS[0] - 27, 1095, 105, "none",
                stroke=SILKSCREEN, stroke_width=3)
    for i in range(g.HEADER_COLUMNS):
        for y in g.HEADER_ROW_YS:
            centre = (g.HEADER_X + g.PITCH * i, y)
            canvas.circle(centre, 17, HEADER_COPPER)
            canvas.circle(centre, 8, "#555")


def _draw_pads(canvas: Canvas, highlighted: dict[str, str]) -> None:
    for name in g.PADS:
        centre = g.pad(name)
        colour = highlighted.get(name)
        if colour:
            canvas.circle(centre, 16, COPPER, colour, 6)
        else:
            canvas.circle(centre, 16, COPPER)
        canvas.circle(centre, 7, DRILL)
        weight = ' font-weight="bold"' if colour else ""
        canvas.add(f'<text transform="translate({centre[0] + 7:.1f},{g.PAD_Y + 30}) rotate(-90)" '
                   f'text-anchor="end" font-size="20"{weight} fill="{colour or SILKSCREEN}">{name}</text>')


def _draw_rails_and_strips(canvas: Canvas) -> None:
    _draw_rail_box(canvas, [g.FIVE_VOLT], "5V")
    _draw_rail_box(canvas, [g.THREE_VOLT], "3.3V")
    _draw_rail_box(canvas, list(g.GROUND), "GND")
    for column in g.COLUMNS:
        if column in g.STRIP_COLUMNS:
            _draw_strip(canvas, column, "A", "C")
            _draw_strip(canvas, column, "D", "F")
        else:
            _draw_strip(canvas, column, "A", "D")
    # The two GND columns are joined across the top.
    canvas.rect(g.column_x(g.GROUND[0]), g.row_y("A") - 9, g.PITCH, 18, COPPER)


def _draw_rail_box(canvas: Canvas, columns: list[int], label: str) -> None:
    x0, x1 = g.column_x(columns[0]) - 28, g.column_x(columns[-1]) + 28
    canvas.rect(x0, g.row_y("A") - 30, x1 - x0, g.row_y("D") - g.row_y("A") + 60, "none",
                stroke=SILKSCREEN, stroke_width=2.5)
    canvas.text(((x0 + x1) / 2, g.row_y("D") + 62), label, 20, SILKSCREEN, anchor="middle")


def _draw_strip(canvas: Canvas, column: int, first_row: str, last_row: str) -> None:
    x, top, bottom = g.column_x(column), g.row_y(first_row), g.row_y(last_row)
    canvas.rect(x - 14, top - 14, 28, bottom - top + 28, COPPER, rx=14)


def _draw_holes(canvas: Canvas) -> None:
    for column in g.COLUMNS:
        for row in g.rows_of(column):
            canvas.circle(g.hole(f"{column}{row}"), 7, DRILL)


def _draw_grid_names(canvas: Canvas) -> None:
    for column in g.COLUMNS:
        canvas.text((g.column_x(column), g.ORIGIN_Y + 910), str(column), 17, GRID_NOTE, anchor="middle")
    right_of_board = g.BOARD_X + g.BOARD_WIDTH + 22
    for row in g.ROWS:
        canvas.text((right_of_board, g.row_y(row) + 7), row, 20, GRID_NOTE)
