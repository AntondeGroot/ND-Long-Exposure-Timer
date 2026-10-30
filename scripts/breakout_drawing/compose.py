"""Pages: the overview with every step, and one page per step.

A step page shows the steps before it faded - already on the board - its own parts at
full strength, and nothing that comes later. A step that puts parts under the board
shows them a second time, from underneath.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from . import geometry as g
from .board import draw_board, draw_region
from .layout import NOTES, PAD_COLOURS, REGIONS, STEPS
from .parts import Jumper, Part, SolderBridge, Wire, badge
from .svg import Canvas

WIDTH = 1510
LEGEND_TOP = 930
UNDERSIDE_HEIGHT = 860
UNDERSIDE_BOARD_GAP = 90  # from the underside view's heading down to the board
UNDERSIDE_NOTE = (
    "Turned over left to right: the header still at the top, column 1 now on the right. The wires show solid here."
)
LINE_HEIGHT = 42
NOTE_HEIGHT = 32
DONE_OPACITY = 0.3
BULLET = "#555"
WARNING = "#c92a2a"
STRIPS = "Top view, header at the top. Strips: rows A-C and D-F of each column are joined; nothing else is."


def overview() -> str:
    """The whole build at once: what the board looks like when it is finished.

    Only a preview. Built in this order the parts fit; soldered straight from this
    picture they do not, because the adapter lies over holes earlier parts go in.
    """
    wires = [part for step in STEPS for part in step.parts if isinstance(part, Wire)]
    return _page(
        f"Preview: the finished board, built in {len(STEPS)} steps",
        done=[],
        current=[part for step in STEPS for part in step.parts],
        legend_title="Wires that leave the board",
        legend=wires,
        subtitle=(f"Don't solder from this picture: follow steps 1 to {len(STEPS)} in order.", WARNING),
        steps=[f"Step {number}: {step.title}" for number, step in enumerate(STEPS, start=1)],
    )


def step_page(number: int) -> str:
    """Step `number`, counting from 1."""
    step = STEPS[number - 1]
    done = [part for earlier in STEPS[: number - 1] for part in earlier.parts]
    return _page(
        f"Breakout board, step {number} of {len(STEPS)}: {step.title}",
        done=done,
        current=list(step.parts),
        legend_title="This step",
        legend=list(step.parts),
        underside=[part for part in step.parts if _under_the_board(part)],
    )


def _page(
    title: str,
    done: list[Part],
    current: list[Part],
    legend_title: str,
    legend: list[Part],
    subtitle: tuple[str, str] = (STRIPS, "#444"),
    steps: list[str] | None = None,
    underside: list[Part] | None = None,
) -> str:
    steps, underside = steps or [], underside or []
    in_two_columns = all(isinstance(part, Wire) for part in legend)
    below_board = LEGEND_TOP + (UNDERSIDE_HEIGHT if underside else 0)
    steps_height = (len(steps) + 2) * LINE_HEIGHT if steps else 0
    legend_height = 60 + _legend_lines(legend, in_two_columns) * LINE_HEIGHT + len(NOTES) * NOTE_HEIGHT + 40
    canvas = Canvas(WIDTH, below_board + steps_height + legend_height)
    _draw_title(canvas, title, subtitle)
    pads = _highlighted_pads([*done, *current])
    draw_board(canvas, pads)
    for region in REGIONS:
        draw_region(canvas, region)
    with canvas.faded(DONE_OPACITY):
        _draw_parts(canvas, done)
    _draw_parts(canvas, current)
    _draw_underside(canvas, underside, pads)
    _draw_steps(canvas, steps, top=below_board)
    _draw_legend(canvas, legend_title, legend, in_two_columns, top=below_board + steps_height)
    return canvas.svg()


def _under_the_board(part: Part) -> bool:
    return isinstance(part, SolderBridge) or (isinstance(part, Jumper) and part.underneath)


def _draw_underside(canvas: Canvas, parts: list[Part], pads: dict[str, str]) -> None:
    """The board turned over, with the parts under it: what you see while soldering them."""
    if not parts:
        return
    canvas.text((40, LEGEND_TOP + 10), "The same step, seen from underneath", 30, bold=True)
    canvas.text((40, LEGEND_TOP + 46), UNDERSIDE_NOTE, 21, "#444")
    with canvas.mirrored(g.BOARD_X + g.BOARD_WIDTH / 2, LEGEND_TOP + UNDERSIDE_BOARD_GAP - g.BOARD_Y):
        draw_board(canvas, pads)
        # From underneath the wires are in plain sight, so they are drawn solid.
        _draw_parts(canvas, [replace(part, underneath=False) if isinstance(part, Jumper) else part for part in parts])


def _draw_title(canvas: Canvas, title: str, subtitle: tuple[str, str]) -> None:
    text, colour = subtitle
    canvas.text((40, 60), title, 34, bold=True)
    canvas.text((40, 100), text, 21, colour, bold=colour == WARNING)


def _draw_steps(canvas: Canvas, steps: list[str], top: float) -> None:
    """The steps the overview is built in, each with its own drawing further down."""
    if not steps:
        return
    canvas.text((80, top), "Built in these steps, each drawn on its own below", 22, bold=True)
    for i, step in enumerate(steps):
        y = top + 44 + i * LINE_HEIGHT
        canvas.circle((95, y - 7), 6, BULLET)
        canvas.text((122, y), step, 20, "#222")


def _highlighted_pads(parts: Iterable[Part]) -> dict[str, str]:
    return {pad: PAD_COLOURS[pad] for part in parts for pad in part.pads()}


def _draw_parts(canvas: Canvas, parts: Iterable[Part]) -> None:
    for part in parts:
        part.draw(canvas)


def _legend_lines(parts: list[Part], in_two_columns: bool) -> int:
    """Wires are short enough to list two to a line; parts get a line each."""
    return (len(parts) + 1) // 2 if in_two_columns else len(parts)


def _draw_legend(canvas: Canvas, title: str, parts: list[Part], in_two_columns: bool, top: float) -> None:
    canvas.text((80, top), title, 22, bold=True)
    for i, part in enumerate(parts):
        column, line = (i % 2, i // 2) if in_two_columns else (0, i)
        x, y = 80 + column * 780, top + 44 + line * LINE_HEIGHT
        if isinstance(part, Wire):
            badge(canvas, (x + 15, y - 7), part.number, part.colour)
        else:
            canvas.circle((x + 15, y - 7), 6, BULLET)
        canvas.text((x + 42, y), part.describe(), 20, "#222")
    notes_top = top + 44 + _legend_lines(parts, in_two_columns) * LINE_HEIGHT + 10
    for i, note in enumerate(NOTES):
        canvas.text((80, notes_top + i * NOTE_HEIGHT), note, 19, "#444")
