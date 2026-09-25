"""The panel driven straight from spidev and lgpio, for the boot splash.

The vendor driver works, but importing it costs 9.2s of the splash's 18.5s at
boot - almost all of it `gpiozero`, which `epdconfig` imports and instantiates at
import time. The panel work underneath is 2.4s. This is that 2.4s without the
9.2s: the same command sequence as `waveshare_epd.epd2in13_V4`, over the same SPI
settings, with the four pins read and written through `lgpio` directly.

main.py already declined gpiozero for the buttons, for a different reason - its
lgpio backend busy-loops - so this is the same trade a second time.

Only what the splash needs is here: initialise, push one full frame, sleep. No
partial refresh, no fast mode, no reading the temperature sensor. The application
keeps using the vendor driver, which is welcome to take its time.
"""

from __future__ import annotations

import time

# The panel's own geometry, and the pins the HAT wires it to (BCM numbering).
WIDTH = 122
HEIGHT = 250
RESET_PIN = 17
DATA_COMMAND_PIN = 25
POWER_PIN = 18
BUSY_PIN = 24

# Chip select is driven by the SPI peripheral, not by us - which is why the
# vendor driver's writes to its cs_pin are commented out at both ends.
SPI_BUS = 0
SPI_DEVICE = 0
SPI_HZ = 4_000_000
SPI_MODE = 0b00

# How long the controller is allowed to stay busy before we give up on it. The
# vendor driver waits for ever; at boot, for ever is the wrong answer - the unit
# would sit there until systemd killed it, with nothing in the journal.
BUSY_TIMEOUT_SECONDS = 15.0
BUSY_POLL_SECONDS = 0.01

# The splash runs early enough to beat udev to the GPIO character device. The
# node is created root-only and only then chowned to the gpio group by
# 99-com.rules, and arriving in between reads as lgpio.error('can not open
# gpiochip') - which is exactly what the first boot on the new ordering did, at
# 24.8s. Waiting is the whole point of starting early, so it waits.
GPIO_CHIP = 0
GPIO_WAIT_SECONDS = 20.0
GPIO_POLL_SECONDS = 0.05
SPI_WAIT_SECONDS = 20.0
SPI_POLL_SECONDS = 0.05


class PanelBusy(RuntimeError):
    """The controller never released BUSY, so the frame was never drawn."""


class Panel:
    """The 2in13 V4, speaking the sequence its datasheet asks for.

    `gpio` and `spi` are injected so the sequence can be tested off the hardware;
    `open()` supplies the real ones.
    """

    def __init__(self, gpio, spi) -> None:
        self._gpio = gpio
        self._spi = spi

    @classmethod
    def open(cls) -> Panel:
        """Claim the pins and the bus. Imports cost ~0.5s, against gpiozero's 3s."""
        import lgpio
        import spidev

        # The bus first, and the pins only once it is ours. Claiming a pin is
        # visible to the panel and to the application - a half-opened splash that
        # sat on RESET for five seconds while the application initialised the
        # panel behind it is what filled the screen with noise once already.
        spi = _open_spi_when_ready(spidev)
        try:
            chip = _open_chip_when_ready(lgpio)
        except BaseException:
            spi.close()
            raise

        # RESET is active low, so it is claimed high: idle, not asserted.
        lgpio.gpio_claim_output(chip, RESET_PIN, 1)
        for pin in (DATA_COMMAND_PIN, POWER_PIN):
            lgpio.gpio_claim_output(chip, pin, 0)
        lgpio.gpio_claim_input(chip, BUSY_PIN, lgpio.SET_PULL_NONE)

        return cls(_LgpioPins(lgpio, chip), spi)

    # ----------------------------------------------------------------- the panel

    def init(self) -> None:
        """Power up, reset, and set the panel to take one full 122x250 frame."""
        self._gpio.write(POWER_PIN, 1)
        self._reset()
        self._wait_until_idle()

        self._command(0x12)  # software reset
        self._wait_until_idle()

        self._command(0x01, 0xF9, 0x00, 0x00)  # driver output control
        self._command(0x11, 0x03)  # data entry mode: x and y both increment

        # The window is set in bytes across and rows down, so the x values are
        # shifted by three exactly as the vendor driver shifts them.
        self._command(0x44, 0x00, (WIDTH - 1) >> 3)
        self._command(0x45, 0x00, 0x00, (HEIGHT - 1) & 0xFF, (HEIGHT - 1) >> 8)
        self._command(0x4E, 0x00)  # cursor x
        self._command(0x4F, 0x00, 0x00)  # cursor y

        self._command(0x3C, 0x05)  # border waveform
        self._command(0x21, 0x00, 0x80)  # display update control
        self._command(0x18, 0x80)  # use the built-in temperature sensor
        self._wait_until_idle()

    def display(self, buffer) -> None:
        """Write one packed frame into RAM and run the update sequence."""
        self._command(0x24)
        self._data(buffer)
        self._command(0x22, 0xF7)  # full update
        self._command(0x20)  # go
        self._wait_until_idle()

    def sleep(self) -> None:
        """Deep sleep, then drop the bus and the rails.

        E-paper holds its image unpowered, so this is what lets the splash
        survive until the application draws over it - and it releases the pins
        the application wants.
        """
        self._command(0x10, 0x01)
        time.sleep(2.0)  # the controller wants this before power goes

        self._spi.close()
        for pin in (RESET_PIN, DATA_COMMAND_PIN, POWER_PIN):
            self._gpio.write(pin, 0)
        self._gpio.close()

    def abandon(self) -> None:
        """Let everything go, in a hurry, without asserting anything.

        For a failure part-way through: closing the chip returns the pins to
        inputs, where they cannot hold the panel in reset while the application
        tries to drive it.
        """
        try:
            self._spi.close()
        finally:
            self._gpio.close()

    # ------------------------------------------------------------------ the wire

    def _reset(self) -> None:
        for level, pause in ((1, 0.020), (0, 0.002), (1, 0.020)):
            self._gpio.write(RESET_PIN, level)
            time.sleep(pause)

    def _command(self, command: int, *data: int) -> None:
        self._gpio.write(DATA_COMMAND_PIN, 0)
        self._spi.writebytes([command])
        for byte in data:
            self._data([byte])

    def _data(self, buffer) -> None:
        self._gpio.write(DATA_COMMAND_PIN, 1)
        self._spi.writebytes2(buffer)

    def _wait_until_idle(self) -> None:
        """BUSY high means working. Bounded, unlike the vendor's while loop."""
        deadline = time.monotonic() + BUSY_TIMEOUT_SECONDS
        while self._gpio.read(BUSY_PIN) == 1:
            if time.monotonic() > deadline:
                raise PanelBusy(f"BUSY still high after {BUSY_TIMEOUT_SECONDS}s")
            time.sleep(BUSY_POLL_SECONDS)


class _LgpioPins:
    """The three writes and one read this needs, against a real chip."""

    def __init__(self, lgpio, chip) -> None:
        self._lgpio = lgpio
        self._chip = chip

    def write(self, pin: int, level: int) -> None:
        self._lgpio.gpio_write(self._chip, pin, level)

    def read(self, pin: int) -> int:
        return self._lgpio.gpio_read(self._chip, pin)

    def close(self) -> None:
        self._lgpio.gpiochip_close(self._chip)


def _open_spi_when_ready(spidev):
    """The SPI bus, once it is ours to open.

    /dev/spidev0.0 exists long before it is readable: it is created root-only and
    chowned to the spi group by udev's coldplug pass, which on this card lands
    around 41s. Same race as the GPIO chip, one device later - the first boot on
    the new ordering waited 16s for the chip and then died here.
    """
    deadline = time.monotonic() + SPI_WAIT_SECONDS
    while True:
        spi = spidev.SpiDev()
        try:
            spi.open(SPI_BUS, SPI_DEVICE)
        except (PermissionError, FileNotFoundError):
            if time.monotonic() > deadline:
                raise
            time.sleep(SPI_POLL_SECONDS)
            continue
        spi.max_speed_hz = SPI_HZ
        spi.mode = SPI_MODE
        return spi


def _open_chip_when_ready(lgpio, chip: int = GPIO_CHIP):
    """The GPIO chip, once it is ours to open.

    Not a retry for its own sake: at this point in the boot the device node
    reliably exists before its permissions do, so the first attempt failing is
    the normal case rather than a fault.
    """
    deadline = time.monotonic() + GPIO_WAIT_SECONDS
    while True:
        try:
            return lgpio.gpiochip_open(chip)
        except lgpio.error:
            if time.monotonic() > deadline:
                raise
            time.sleep(GPIO_POLL_SECONDS)
