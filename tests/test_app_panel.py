"""How the application opens the panel, which is most of what it costs to start.

Opening it was measured at 6.2s of a boot that is ready at 61s, and the two white
frames were the larger part. They exist for a panel left in an unknown state, so
the thing worth pinning is exactly when they are skipped and when they are not.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MAIN = Path(__file__).resolve().parent.parent / "main.py"
_spec = importlib.util.spec_from_file_location("nd_timer_main", _MAIN)
main_module = importlib.util.module_from_spec(_spec)


@pytest.fixture(scope="module", autouse=True)
def loaded():
    """main.py imports the panel driver lazily, so it loads off the Pi."""
    _spec.loader.exec_module(main_module)


class FakeEPD:
    """Records what the panel was asked to do, in order."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.last_frame = None

    def init(self) -> None:
        self.calls.append("init")

    def display(self, buffer) -> None:
        self.calls.append("display")
        self.last_frame = buffer

    def sleep(self) -> None:
        self.calls.append("sleep")


@pytest.fixture
def epd(monkeypatch):
    """The panel driver, replaced by a FakeEPD that records what it is asked."""
    panel = FakeEPD()
    monkeypatch.setattr(main_module, "open_panel", lambda: panel)
    return panel


def test_a_panel_the_splash_drew_this_boot_is_not_cleared_to_white_again(epd):
    # The splash has just done a complete refresh, so the panel's state is
    # known and the first real screen replaces it cleanly. Initialised, but
    # nothing displayed: the white frames are the seconds this saves.
    main_module.Panel(splash_drawn=True)

    assert epd.calls == ["init"]


def test_a_panel_nothing_has_drawn_this_boot_is_still_cleared_to_white(epd):
    # No word from the splash - a power cut, a splash that failed, or none
    # installed - means the panel may hold a half-finished refresh. Exactly
    # once: a second pass costs over two seconds and was never shown to be
    # needed, so a test that allowed either would hide it creeping back.
    main_module.Panel(splash_drawn=False)

    assert epd.calls == ["init", "display"]


def test_a_stopping_app_leaves_the_switched_off_screen_and_then_sleeps_the_panel(epd):
    # E-paper keeps its last image unpowered, so a device left showing its last
    # screen looks switched on. Initialised again first: systemd's SIGINT can
    # land in the middle of a refresh, and a reset is what gets the panel out of
    # one.
    panel = main_module.Panel(splash_drawn=True)
    epd.calls.clear()

    panel.leave_switched_off()

    switched_off = main_module.render_splash(main_module.SplashScreen(message="switched off", version=""))
    assert epd.calls == ["init", "display", "sleep"]
    assert epd.last_frame == list(main_module.to_panel_bytes(switched_off))
