"""The splash that runs before the application, on a Pi that boots slowly.

Its whole reason to exist is speed: a blank panel for a minute reads as a device
that did not switch on. So the tests cover the two ways it can decline to run,
the bytes it pushes, and the one import it must never acquire.
"""

import ast
from pathlib import Path

import pytest

from nd_timer import boot_splash


class FakeEPD:
    """Records what it was asked to do, which is the whole contract."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.written: list[bytes] = []

    def init(self) -> None:
        self.calls.append("init")

    def display(self, buffer) -> None:
        self.calls.append("display")
        self.written.append(bytes(buffer))

    def sleep(self) -> None:
        self.calls.append("sleep")


@pytest.fixture(autouse=True)
def marker(monkeypatch, tmp_path):
    """Where the splash leaves word, moved off the real /run for every test.

    Both markers - drawn, and done - though only the first is returned.

    Autouse because any test that draws successfully writes it, and on a Linux
    machine running as root that would be the real marker the application reads.
    """
    drawn = tmp_path / "splash-drawn"
    monkeypatch.setattr(boot_splash, "DRAWN_MARKER", drawn)
    monkeypatch.setattr(boot_splash, "DONE_MARKER", tmp_path / "splash-done")
    return drawn


@pytest.fixture
def panel(monkeypatch, tmp_path):
    """boot_splash wired to a fake panel instead of the real hardware.

    SPI_DEVICE is pointed at something that exists because the unit now starts
    before udev has necessarily made the real node, so main() waits for it.
    """
    epd = FakeEPD()
    monkeypatch.setattr(boot_splash, "open_panel", lambda: epd)
    monkeypatch.setattr(boot_splash, "SPI_DEVICE", tmp_path)
    return epd


@pytest.fixture
def splash(monkeypatch, tmp_path):
    """A packed buffer on disk, standing in for assets/splash.bin."""
    packed = tmp_path / "splash.bin"
    packed.write_bytes(bytes(range(256)) * 4)
    monkeypatch.setattr(boot_splash, "SPLASH_BUFFER", packed)
    return packed


def test_a_missing_buffer_is_reported_rather_than_left_to_fail_later(monkeypatch, tmp_path, capsys):
    # This runs unattended at boot with nobody watching, so the only useful
    # failure is one that says what is missing and how it is made.
    monkeypatch.setattr(boot_splash, "SPLASH_BUFFER", tmp_path / "absent.bin")

    assert boot_splash.main() == 1
    complaint = capsys.readouterr().err
    assert "absent.bin" in complaint
    assert "render-screens.py" in complaint


def test_a_transport_that_is_not_installed_is_reported(monkeypatch, splash, tmp_path, capsys):
    # Off the Pi - or before setup-pi.sh has run - lgpio and spidev are absent.
    # That is a normal state, not a crash worth a traceback in the boot log.
    def no_lgpio():
        raise ImportError("No module named 'lgpio'")

    monkeypatch.setattr(boot_splash, "open_panel", no_lgpio)
    monkeypatch.setattr(boot_splash, "SPI_DEVICE", tmp_path)

    assert boot_splash.main() == 1
    assert "lgpio" in capsys.readouterr().err


def test_the_packed_buffer_reaches_the_panel_byte_for_byte(panel, splash):
    # Packed at build time precisely so nothing here has to interpret it. If it
    # were re-encoded on the way through, that would defeat the point.
    assert boot_splash.main() == 0

    assert panel.written == [splash.read_bytes()]


def test_the_panel_is_woken_written_and_put_back_to_sleep(panel, splash):
    # The sleep is not power saving - it is what lets the image survive the gap
    # until the application starts. An awake controller bleeds what it is
    # holding, which reads as a screen slowly fading to grey.
    boot_splash.main()

    assert panel.calls == ["init", "display", "sleep"]


def test_it_does_not_import_pillow():
    # The module's reason for existing. Importing Pillow on an ARMv6 Pi costs
    # several seconds, which is most of the blank-panel time this exists to
    # remove - so the constraint is checked rather than left to a comment.
    source = ast.parse(Path(boot_splash.__file__).read_text())
    imported = set()
    for node in ast.walk(source):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not [name for name in imported if name.split(".")[0] == "PIL"], (
        f"boot_splash must not import Pillow; it imports {sorted(imported)}"
    )


def test_a_failure_part_way_through_lets_the_pins_go(monkeypatch, splash, tmp_path, capsys):
    # The boot this pins: the splash claimed RESET, DC and POWER, then died, and
    # held them for five seconds while the application initialised the panel
    # behind it. The screen filled with random pixels. Whatever goes wrong, the
    # pins have to be released rather than left asserted.
    class FailingPanel:
        def __init__(self) -> None:
            self.abandoned = False

        def init(self) -> None:
            raise RuntimeError("BUSY still high after 15.0s")

        def abandon(self) -> None:
            self.abandoned = True

    failing = FailingPanel()
    monkeypatch.setattr(boot_splash, "open_panel", lambda: failing)
    monkeypatch.setattr(boot_splash, "SPI_DEVICE", tmp_path)

    assert boot_splash.main() == 1
    assert failing.abandoned, "the pins were left claimed"
    assert "BUSY still high" in capsys.readouterr().err


def test_a_drawn_splash_leaves_word_for_the_application(panel, splash, marker):
    # The application skips its white frame on this word alone, so it is
    # only worth anything if a complete draw is what writes it.
    assert boot_splash.main() == 0

    assert marker.exists()


def test_a_splash_that_failed_part_way_leaves_no_word(monkeypatch, splash, tmp_path, marker):
    # A draw that died part-way leaves the panel in exactly the unknown state
    # the application's white frame is there for. Word written anyway would
    # skip it, and the first real screen would go onto half a refresh.
    class FailingPanel:
        def init(self) -> None:
            pass

        def display(self, buffer) -> None:
            raise RuntimeError("BUSY still high after 15.0s")

        def abandon(self) -> None:
            pass

    monkeypatch.setattr(boot_splash, "open_panel", FailingPanel)
    monkeypatch.setattr(boot_splash, "SPI_DEVICE", tmp_path)

    assert boot_splash.main() == 1
    assert not marker.exists()


def test_a_marker_that_cannot_be_written_does_not_fail_the_splash(monkeypatch, panel, splash, tmp_path, capsys):
    # By then the frame is on the glass. The marker only saves the application
    # a white frame, so losing it costs two seconds - reported, but not a
    # failed unit in the boot log over a splash that worked.
    monkeypatch.setattr(boot_splash, "DRAWN_MARKER", tmp_path / "no-such-dir" / "splash-drawn")

    assert boot_splash.main() == 0
    assert "could not leave word" in capsys.readouterr().err


def test_the_application_waits_until_the_splash_has_let_go_of_the_panel(monkeypatch, splash, tmp_path):
    # The two processes must never drive the panel at once - that is what put
    # noise on the screen on 2026-09-24. So with a splash installed and not yet
    # done, the wait has to hold, however many looks it takes.
    unit = tmp_path / "nd-timer-splash.service"
    unit.touch()
    monkeypatch.setattr(boot_splash, "SPLASH_UNIT", unit)
    looks = []

    def a_splash_that_finishes_on_the_third_look(_seconds):
        looks.append(_seconds)
        if len(looks) == 3:
            boot_splash.DONE_MARKER.touch()

    monkeypatch.setattr(boot_splash.time, "sleep", a_splash_that_finishes_on_the_third_look)

    assert boot_splash.wait_for_splash() is True
    assert len(looks) == 3


def test_without_a_splash_installed_the_application_does_not_wait(monkeypatch, splash, tmp_path):
    # A device set up without the splash would otherwise sit out the whole
    # timeout on every boot, waiting for a marker nothing is going to write.
    monkeypatch.setattr(boot_splash, "SPLASH_UNIT", tmp_path / "not-installed.service")
    looks = []
    monkeypatch.setattr(boot_splash.time, "sleep", looks.append)

    assert boot_splash.wait_for_splash() is True
    assert looks == []


def test_a_splash_that_never_says_it_is_done_is_given_up_on(monkeypatch, splash, tmp_path):
    # A splash killed by its own timeout never reaches the line that writes the
    # marker. The application has to start regardless - late, once, rather
    # than never - and say that it gave up rather than that the splash finished.
    unit = tmp_path / "nd-timer-splash.service"
    unit.touch()
    monkeypatch.setattr(boot_splash, "SPLASH_UNIT", unit)
    monkeypatch.setattr(boot_splash, "SPLASH_DONE_WAIT_SECONDS", 0.05)
    monkeypatch.setattr(boot_splash, "SPLASH_DONE_POLL_SECONDS", 0.01)

    assert boot_splash.wait_for_splash() is False


def test_the_splash_says_it_is_done_even_when_it_failed(monkeypatch, splash, tmp_path):
    # Done means "the panel is free", not "the panel was drawn". A splash that
    # dies on something nobody anticipated - here an exception main() does not
    # catch - has still let go of the panel, and an application left waiting
    # for it would sit out the whole timeout for nothing.
    def a_panel_that_cannot_be_opened():
        raise RuntimeError("something nobody anticipated")

    monkeypatch.setattr(boot_splash, "open_panel", a_panel_that_cannot_be_opened)
    monkeypatch.setattr(boot_splash, "SPI_DEVICE", tmp_path)

    with pytest.raises(RuntimeError):
        boot_splash.main()

    assert boot_splash.DONE_MARKER.exists()
