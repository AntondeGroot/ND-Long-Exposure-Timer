"""The panel must be asleep whenever it is not being written to.

Left awake the controller holds a bias voltage on the pixels and the image
bleeds out of them, fading to grey over minutes. Nothing catches that until
someone looks at an idle device, so it is pinned here instead.
"""

import sys
import types

import pytest


class FakeEPD:
    """Records the order it was driven in, which is the whole point."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def init(self) -> None:
        self.calls.append("init")

    def display(self, frame) -> None:
        self.calls.append("display")

    def sleep(self) -> None:
        self.calls.append("sleep")


@pytest.fixture
def panel(monkeypatch):
    """main.Panel, wired to a fake driver instead of the real hardware."""
    epd = FakeEPD()
    module = types.ModuleType("fake_epd")
    module.EPD = lambda: epd
    monkeypatch.setitem(sys.modules, "fake_epd", module)

    import main

    monkeypatch.setattr(main, "PANEL_MODULE", "fake_epd")
    built = main.Panel()
    return built, epd


def test_it_is_left_asleep_once_it_has_started_up(panel):
    _, epd = panel

    assert epd.calls[0] == "init", "it has to be woken before it is written to"
    assert epd.calls[-1] == "sleep", "an awake panel fades the image it is holding"


def test_every_refresh_wakes_the_panel_and_puts_it_back(panel):
    built, epd = panel
    from nd_timer.ui.screens import SplashScreen

    epd.calls.clear()
    built.show(SplashScreen(message="ONE", version="test"))
    built.show(SplashScreen(message="TWO", version="test"))

    assert epd.calls == ["init", "display", "sleep", "init", "display", "sleep"]


def test_an_unchanged_screen_does_not_touch_the_panel_at_all(panel):
    built, epd = panel
    from nd_timer.ui.screens import SplashScreen

    built.show(SplashScreen(message="SAME", version="test"))
    epd.calls.clear()
    built.show(SplashScreen(message="SAME", version="test"))

    assert epd.calls == [], "a refresh costs a second and a little of the panel's life"
