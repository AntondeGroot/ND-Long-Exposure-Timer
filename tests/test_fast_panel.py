"""The panel spoken to directly, without the vendor driver.

This replaces nine seconds of gpiozero import at boot, and the only thing that
makes it safe is that it says exactly what the vendor driver said. So the tests
are transcripts: every command and every data byte, in order.
"""

from __future__ import annotations

import pytest

from nd_timer import fast_panel


class FakeGpio:
    """Records levels, and answers BUSY as idle unless told otherwise."""

    def __init__(self, busy_readings: list[int] | None = None) -> None:
        self.writes: list[tuple[int, int]] = []
        self.levels: dict[int, int] = {}
        self.closed = False
        self._busy = list(busy_readings or [])

    def write(self, pin: int, level: int) -> None:
        self.writes.append((pin, level))
        self.levels[pin] = level

    def read(self, pin: int) -> int:
        return self._busy.pop(0) if self._busy else 0

    def close(self) -> None:
        self.closed = True


class FakeSpi:
    """Records the wire as commands and data, using DC to tell them apart."""

    def __init__(self, gpio: FakeGpio) -> None:
        self._gpio = gpio
        self.transcript: list[tuple[str, object]] = []
        self.closed = False

    def _is_command(self) -> bool:
        return self._gpio.levels.get(fast_panel.DATA_COMMAND_PIN) == 0

    def writebytes(self, values) -> None:
        kind = "cmd" if self._is_command() else "data"
        self.transcript.append((kind, list(values)[0] if kind == "cmd" else list(values)))

    def writebytes2(self, values) -> None:
        self.transcript.append(("data", list(values)))

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def panel():
    gpio = FakeGpio()
    spi = FakeSpi(gpio)
    return fast_panel.Panel(gpio, spi), gpio, spi


def test_init_speaks_the_vendor_drivers_sequence_byte_for_byte(panel):
    # Transcribed from waveshare_epd/epd2in13_V4.py init(): reset, software
    # reset, driver output control, data entry mode, the window and cursor for a
    # full 122x250 frame, border waveform, update control, temperature sensor.
    # The x values are shifted by three because the panel addresses RAM in bytes
    # across, which is why the window's second byte is 15 and not 121.
    epd, gpio, spi = panel

    epd.init()

    assert spi.transcript == [
        ("cmd", 0x12),
        ("cmd", 0x01), ("data", [0xF9]), ("data", [0x00]), ("data", [0x00]),
        ("cmd", 0x11), ("data", [0x03]),
        ("cmd", 0x44), ("data", [0x00]), ("data", [15]),
        ("cmd", 0x45), ("data", [0x00]), ("data", [0x00]), ("data", [249]), ("data", [0x00]),
        ("cmd", 0x4E), ("data", [0x00]),
        ("cmd", 0x4F), ("data", [0x00]), ("data", [0x00]),
        ("cmd", 0x3C), ("data", [0x05]),
        ("cmd", 0x21), ("data", [0x00]), ("data", [0x80]),
        ("cmd", 0x18), ("data", [0x80]),
    ]
    # Power first, then the 1-0-1 hardware reset the datasheet asks for.
    assert gpio.writes[:4] == [
        (fast_panel.POWER_PIN, 1),
        (fast_panel.RESET_PIN, 1),
        (fast_panel.RESET_PIN, 0),
        (fast_panel.RESET_PIN, 1),
    ]


class FakeLgpio:
    """An lgpio whose chip is root-only until the given number of attempts pass."""

    class error(Exception):
        pass

    def __init__(self, failures: int) -> None:
        self.remaining = failures
        self.attempts = 0

    def gpiochip_open(self, chip: int) -> int:
        self.attempts += 1
        if self.remaining > 0:
            self.remaining -= 1
            raise self.error("can not open gpiochip")
        return 7


def test_the_chip_is_opened_once_udev_has_finished_with_it(monkeypatch):
    # The real failure this pins: on the first boot with the early ordering the
    # splash reached gpiochip_open at 24.8s, before 99-com.rules had chowned
    # /dev/gpiochip0 to the gpio group, and lgpio reported 'can not open
    # gpiochip'. Failing attempts are the normal case here, not a fault.
    monkeypatch.setattr(fast_panel, "GPIO_POLL_SECONDS", 0)
    lgpio = FakeLgpio(failures=3)

    assert fast_panel._open_chip_when_ready(lgpio) == 7
    assert lgpio.attempts == 4
