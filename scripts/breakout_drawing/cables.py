"""The two cables from the enclosure wall to the boards, each onto a micro-USB plug.

The power cable only carries power, so it uses the plug's outer two pads. The data
cable carries the camera's USB too, so it uses four; the ID pad stays empty, because
usb-mode.sh puts the Pi's port in host mode rather than leaving it to the ID pin.
"""

from __future__ import annotations

from .cable_page import Cable, CableWire
from .panel_socket import USB_A, USB_C

RED, WHITE, BLUE, BLACK = "#e03131", "#f8f9fa", "#1c7ed6", "#212529"
HEAT_SHRINK_NOTE = "Put heat-shrink over the soldered end of the micro-USB plug."

POWER_CABLE = Cable(
    title="The power cable: USB-C socket to micro-USB plug",
    subtitle="Red to pad 1 (VBUS, +5V), black to pad 5 (GND). The three pads between stay empty.",
    socket=USB_C,
    socket_caption="in the enclosure wall",
    plug_caption="into the UPS HAT's charging port",
    wires=(CableWire(1, "red", RED), CableWire(5, "black", BLACK)),
    notes=("Cable lengths not to scale.", HEAT_SHRINK_NOTE),
)

DATA_CABLE = Cable(
    title="The data cable: USB-A socket to micro-USB plug",
    subtitle="Red to pad 1 (VBUS), white to 2 (D-), blue to 3 (D+), black to 5 (GND). Pad 4 stays empty.",
    socket=USB_A,
    socket_caption="for the camera's cable",
    plug_caption="into the Pi's data port, marked USB",
    wires=(CableWire(1, "red", RED), CableWire(2, "white", WHITE), CableWire(3, "blue", BLUE),
           CableWire(5, "black", BLACK)),
    notes=("Cable lengths not to scale.", HEAT_SHRINK_NOTE,
           "Socket wire colours vary between makers: check white and blue against the socket's D- and D+ "
           "with the meter."),
)
