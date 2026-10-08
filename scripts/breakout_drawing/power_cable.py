"""The power cable: the USB-C socket's red and black wires onto a micro-USB plug.

The socket in the enclosure wall only carries power, so of the plug's five pads only
the outer two are used: VBUS (+5V) and GND. The plug goes into the UPS HAT's charging
port.
"""

from __future__ import annotations

import math

from .micro_usb_plug import PINS, Plug
from .svg import Canvas
from .usb_c_socket import Socket

WIDTH, HEIGHT = 1150, 640
OUTLINE = "#555"
RED, BLACK = "#e03131", "#212529"
UNUSED = "#868e96"

PIN_NAMES = {1: "VBUS +5V", 2: "D-", 3: "D+", 4: "ID", 5: "GND"}
WIRES = {1: ("red", RED), 5: ("black", BLACK)}

SOCKET = Socket(origin_x=170, origin_y=330)
PLUG = Plug(origin_x=700, origin_y=290)
LEGEND_X, LEGEND_TOP, LEGEND_LINE = 960, 200, 30


def power_cable_page() -> str:
    canvas = Canvas(WIDTH, HEIGHT)
    canvas.text((40, 60), "The power cable: USB-C socket to micro-USB plug", 30, bold=True)
    canvas.text((40, 98), "Red to pad 1 (VBUS, +5V), black to pad 5 (GND). The three pads between stay empty.",
                21, "#444")
    for pin, (name, colour) in WIRES.items():
        _wire(canvas, name, colour, pin)
    SOCKET.draw(canvas)
    _socket_caption(canvas)
    PLUG.draw(canvas, used_pins=set(WIRES))
    _pin_numbers(canvas)
    _legend(canvas)
    _notes(canvas)
    return canvas.svg()


def _socket_caption(canvas: Canvas) -> None:
    x, y = SOCKET.origin_x, SOCKET.origin_y + 110
    canvas.text((x, y), "USB-C socket", 18, "#444", anchor="middle", bold=True)
    canvas.text((x, y + 24), "in the enclosure wall", 16, "#666", anchor="middle")


def _pin_numbers(canvas: Canvas) -> None:
    for pin in range(1, PINS + 1):
        x, y = PLUG.pad_label(pin)
        canvas.text((x, y + 5), str(pin), 14, "#111", anchor="middle", bold=True)


def _wire(canvas: Canvas, name: str, colour: str, pin: int) -> None:
    """Out of the back of the socket in line with it, one smooth curve, then straight onto
    its pad. Both handles are a share of the distance covered, so a short wire cannot
    overshoot and double back on itself."""
    (x0, y0), (ahead_x, ahead_y) = SOCKET.wire_exit(name), SOCKET.wire_exit(name, extra=1.0)
    end_x, end_y = PLUG.pad_end(pin)
    approach_x = end_x - 70
    reach = math.hypot(approach_x - x0, end_y - y0) * 0.4
    along = math.hypot(ahead_x - x0, ahead_y - y0)
    handle_x, handle_y = x0 + (ahead_x - x0) / along * reach, y0 + (ahead_y - y0) / along * reach
    d = (f"M {x0:.1f} {y0:.1f} C {handle_x:.1f} {handle_y:.1f} {approach_x - reach:.1f} {end_y:.1f} "
         f"{approach_x:.1f} {end_y:.1f} L {end_x:.1f} {end_y:.1f}")
    canvas.path(d, stroke=OUTLINE, stroke_width=12, stroke_linecap="round")
    canvas.path(d, stroke=colour, stroke_width=9, stroke_linecap="round")


def _legend(canvas: Canvas) -> None:
    canvas.text((LEGEND_X, LEGEND_TOP - 30), "pads", 16, "#444", bold=True)
    for line, pin in enumerate(range(1, PINS + 1)):
        used = pin in WIRES
        label = f"{pin}  {PIN_NAMES[pin]}" + ("" if used else ", not used")
        canvas.text((LEGEND_X, LEGEND_TOP + line * LEGEND_LINE), label, 17, "#222" if used else UNUSED, bold=used)
    canvas.text((PLUG.origin_x + 60, LEGEND_TOP + 5 * LEGEND_LINE + 120), "micro-USB plug, wide side up", 18, "#444",
                anchor="middle", bold=True)
    canvas.text((PLUG.origin_x + 60, LEGEND_TOP + 5 * LEGEND_LINE + 144), "the side with the two latch slots", 16,
                "#666", anchor="middle")


NOTES = [
    "Cable lengths not to scale.",
    "Put heat-shrink over the soldered end of the micro-USB plug.",
]


def _notes(canvas: Canvas) -> None:
    top = HEIGHT - 90
    canvas.text((40, top), "Notes", 20, bold=True)
    for line, note in enumerate(NOTES):
        canvas.text((40, top + 32 + line * 26), f"\u2022  {note}", 18, "#444")
