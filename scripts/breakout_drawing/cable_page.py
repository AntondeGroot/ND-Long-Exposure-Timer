"""One page per cable: a panel socket on the left, its wires, a micro-USB plug on the right.

Both cables in the build are this shape - a socket in the enclosure wall whose wires are
soldered to a micro-USB plug - so the page is drawn from a description of the cable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .micro_usb_plug import PINS, Plug
from .panel_socket import PanelSocket, SocketSpec
from .svg import Canvas

WIDTH, HEIGHT = 1150, 640
OUTLINE = "#555"
UNUSED = "#868e96"
PIN_NAMES = {1: "VBUS +5V", 2: "D-", 3: "D+", 4: "ID", 5: "GND"}

PLUG = Plug(origin_x=700, origin_y=290)
SOCKET_AT = (170, 330)
LEGEND_X, LEGEND_TOP, LEGEND_LINE = 960, 200, 30


@dataclass(frozen=True)
class CableWire:
    pin: int
    name: str
    colour: str


@dataclass(frozen=True)
class Cable:
    title: str
    subtitle: str
    socket: SocketSpec
    socket_caption: str
    plug_caption: str
    wires: tuple[CableWire, ...]
    notes: tuple[str, ...]


def cable_page(cable: Cable) -> str:
    canvas = Canvas(WIDTH, HEIGHT)
    socket = PanelSocket(cable.socket, *SOCKET_AT)
    canvas.text((40, 60), cable.title, 30, bold=True)
    canvas.text((40, 98), cable.subtitle, 21, "#444")
    for wire in cable.wires:
        _wire(canvas, socket, wire)
    socket.draw(canvas)
    _captions(canvas, cable)
    used = {wire.pin for wire in cable.wires}
    PLUG.draw(canvas, used_pins=used)
    _pin_numbers(canvas)
    _legend(canvas, used)
    _notes(canvas, cable.notes)
    return canvas.svg()


def _wire(canvas: Canvas, socket: PanelSocket, wire: CableWire) -> None:
    """Out of the back of the socket in line with it, one smooth curve, then straight onto
    its pad. Both handles are a share of the distance covered, so a short wire cannot
    overshoot and double back on itself."""
    (x0, y0), (ahead_x, ahead_y) = socket.wire_exit(wire.name), socket.wire_exit(wire.name, extra=1.0)
    end_x, end_y = PLUG.pad_end(wire.pin)
    approach_x = end_x - 70
    reach = math.hypot(approach_x - x0, end_y - y0) * 0.4
    along = math.hypot(ahead_x - x0, ahead_y - y0)
    handle_x, handle_y = x0 + (ahead_x - x0) / along * reach, y0 + (ahead_y - y0) / along * reach
    d = (f"M {x0:.1f} {y0:.1f} C {handle_x:.1f} {handle_y:.1f} {approach_x - reach:.1f} {end_y:.1f} "
         f"{approach_x:.1f} {end_y:.1f} L {end_x:.1f} {end_y:.1f}")
    canvas.path(d, stroke=OUTLINE, stroke_width=12, stroke_linecap="round")
    canvas.path(d, stroke=wire.colour, stroke_width=9, stroke_linecap="round")


def _captions(canvas: Canvas, cable: Cable) -> None:
    x, y = SOCKET_AT[0], SOCKET_AT[1] + 110
    canvas.text((x, y), cable.socket.name, 18, "#444", anchor="middle", bold=True)
    canvas.text((x, y + 24), cable.socket_caption, 16, "#666", anchor="middle")
    below_plug = LEGEND_TOP + PINS * LEGEND_LINE + 120
    canvas.text((PLUG.origin_x + 60, below_plug), "micro-USB plug, wide side up", 18, "#444", anchor="middle",
                bold=True)
    canvas.text((PLUG.origin_x + 60, below_plug + 24), cable.plug_caption, 16, "#666", anchor="middle")


def _pin_numbers(canvas: Canvas) -> None:
    for pin in range(1, PINS + 1):
        x, y = PLUG.pad_label(pin)
        canvas.text((x, y + 5), str(pin), 14, "#111", anchor="middle", bold=True)


def _legend(canvas: Canvas, used: set[int]) -> None:
    canvas.text((LEGEND_X, LEGEND_TOP - 30), "pads", 16, "#444", bold=True)
    for line, pin in enumerate(range(1, PINS + 1)):
        label = f"{pin}  {PIN_NAMES[pin]}" + ("" if pin in used else ", not used")
        canvas.text((LEGEND_X, LEGEND_TOP + line * LEGEND_LINE), label, 17, "#222" if pin in used else UNUSED,
                    bold=pin in used)


def _notes(canvas: Canvas, notes: tuple[str, ...]) -> None:
    top = HEIGHT - 64 - 26 * len(notes)
    canvas.text((40, top), "Notes", 20, bold=True)
    for line, note in enumerate(notes):
        canvas.text((40, top + 32 + line * 26), f"•  {note}", 18, "#444")
