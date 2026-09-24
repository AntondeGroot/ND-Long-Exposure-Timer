"""The splash that runs before the application, on a Pi that boots slowly.

Its whole reason to exist is speed: a blank panel for a minute reads as a device
that did not switch on. So the tests cover the two ways it can decline to run,
the bytes it pushes, and the one import it must never acquire.
"""

import ast
import sys
import types
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


@pytest.fixture
def panel(monkeypatch):
    """boot_splash wired to a fake driver instead of the real hardware."""
    epd = FakeEPD()
    module = types.ModuleType("fake_panel")
    module.EPD = lambda: epd
    monkeypatch.setitem(sys.modules, "fake_panel", module)
    monkeypatch.setattr(boot_splash, "PANEL_MODULE", "fake_panel")
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


def test_a_driver_that_is_not_installed_is_reported(monkeypatch, splash, capsys):
    # Off the Pi - or before setup-pi.sh has run - the vendor driver is absent.
    # That is a normal state, not a crash worth a traceback in the boot log.
    monkeypatch.setattr(boot_splash, "PANEL_MODULE", "waveshare_epd.does_not_exist")

    assert boot_splash.main() == 1
    assert "does_not_exist" in capsys.readouterr().err


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
