"""Pages: the overview with every step, and one page per step.

A step page shows the steps before it faded - already on the board - its own parts at
full strength, and nothing that comes later.
"""

from __future__ import annotations

from collections.abc import Iterable

from .board import draw_board, draw_region
from .layout import NOTES, PAD_COLOURS, REGIONS, STEPS
from .parts import Part, Wire, badge
from .svg import Canvas

WIDTH = 1510
LEGEND_TOP = 930
LINE_HEIGHT = 42
NOTE_HEIGHT = 32
DONE_OPACITY = 0.3
BULLET = "#555"


def overview() -> str:
    """The whole build at once: what the board looks like when it is finished."""
    wires = [part for step in STEPS for part in step.parts if isinstance(part, Wire)]
    return _page("Breakout Pi Zero - the whole build",
                 done=[], current=[part for step in STEPS for part in step.parts],
                 legend_title="Wires that leave the board", legend=wires)


def step_page(number: int) -> str:
    """Step `number`, counting from 1."""
    step = STEPS[number - 1]
    done = [part for earlier in STEPS[:number - 1] for part in earlier.parts]
    return _page(f"Step {number} of {len(STEPS)}: {step.title}",
                 done=done, current=list(step.parts),
                 legend_title="This step", legend=list(step.parts))


def _page(title: str, done: list[Part], current: list[Part], legend_title: str, legend: list[Part]) -> str:
    in_two_columns = all(isinstance(part, Wire) for part in legend)
    height = LEGEND_TOP + 60 + _legend_lines(legend, in_two_columns) * LINE_HEIGHT + len(NOTES) * NOTE_HEIGHT + 40
    canvas = Canvas(WIDTH, height)
    _draw_title(canvas, title)
    draw_board(canvas, _highlighted_pads([*done, *current]))
    for region in REGIONS:
        draw_region(canvas, region)
    with canvas.faded(DONE_OPACITY):
        _draw_parts(canvas, done)
    _draw_parts(canvas, current)
    _draw_legend(canvas, legend_title, legend, in_two_columns)
    return canvas.svg()


def _draw_title(canvas: Canvas, title: str) -> None:
    canvas.text((40, 60), title, 34, bold=True)
    canvas.text((40, 100), "Top view, header at the top. Strips: rows A-C and D-F of each column are joined; "
                "nothing else is.", 21, "#444")


def _highlighted_pads(parts: Iterable[Part]) -> dict[str, str]:
    return {pad: PAD_COLOURS[pad] for part in parts for pad in part.pads()}


def _draw_parts(canvas: Canvas, parts: Iterable[Part]) -> None:
    for part in parts:
        part.draw(canvas)


def _legend_lines(parts: list[Part], in_two_columns: bool) -> int:
    """Wires are short enough to list two to a line; parts get a line each."""
    return (len(parts) + 1) // 2 if in_two_columns else len(parts)


def _draw_legend(canvas: Canvas, title: str, parts: list[Part], in_two_columns: bool) -> None:
    canvas.text((80, LEGEND_TOP), title, 22, bold=True)
    for i, part in enumerate(parts):
        column, line = (i % 2, i // 2) if in_two_columns else (0, i)
        x, y = 80 + column * 780, LEGEND_TOP + 44 + line * LINE_HEIGHT
        if isinstance(part, Wire):
            badge(canvas, (x + 15, y - 7), part.number, part.colour)
        else:
            canvas.circle((x + 15, y - 7), 6, BULLET)
        canvas.text((x + 42, y), part.describe(), 20, "#222")
    notes_top = LEGEND_TOP + 44 + _legend_lines(parts, in_two_columns) * LINE_HEIGHT + 10
    for i, note in enumerate(NOTES):
        canvas.text((80, notes_top + i * NOTE_HEIGHT), note, 19, "#444")
