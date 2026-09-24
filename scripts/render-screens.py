#!/usr/bin/env python3
"""Render every screen to docs/screens/, for the README and for regression tests.

These images are committed. They document what the device looks like without
needing the hardware, and because they are byte-compared by the test suite, an
accidental visual change shows up as a failing test rather than as a surprise on
the panel weeks later.

Run after any deliberate UI change:  ./scripts/render-screens.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nd_timer.bag import Bag  # noqa: E402
from nd_timer.exposure import COMMON_FILTERS  # noqa: E402
from nd_timer.ui.screens import (  # noqa: E402
    CountdownScreen,
    DelayScreen,
    MainScreen,
    SplashScreen,
    render_countdown,
    render_delay,
    render_main,
    render_splash,
)
from nd_timer.ui.settings import SettingsEntry, SettingsScreen, render_settings  # noqa: E402

# A typical bag: a light filter for water, a medium one and a big stopper.
TYPICAL_BAG = Bag(tuple(f for f in COMMON_FILTERS if f.name in ("ND8", "ND64", "ND1000")))

OUTPUT_DIR = REPO / "docs" / "screens"

# The splash is also written as a packed panel buffer, so the boot-time script can
# push it without importing Pillow - which costs seconds on an armv6 Pi, spent
# staring at a blank panel.
SPLASH_BUFFER = REPO / "assets" / "splash.bin"

# Upscaled copies for the README: 250x122 is unreadably small on a web page, and
# nearest-neighbour keeps the pixels honest rather than blurring them.
README_SCALE = 3

# One case per state worth documenting - and worth noticing a change to. The
# recipes are real: each one is what nd_timer.recipe solves for that scene and
# that time, so the screens in the README cannot drift away from the arithmetic.
CASES = {
    "splash": SplashScreen(message="starting up...", version="v0.1"),
    # A waterfall, metered at 1/60 f/11: two thirds of a second wants ND64, and
    # a third of a stop of ISO is what lands it there. A tenth of a stop is left
    # over, which is closer than the camera can be set and is said anyway - it
    # is how this screen differs from the one a tenth of a stop along.
    "main-waterfall": MainScreen(
        mode="WATERFALL", iso="160", aperture="f/11", nd_label="64", off_by="+0.1st", is_auto=True,
        selected="MODE", base_shutter="1/60 s", final_time="0.7 s",
        setting_time=False, shows_nudge_hint=False, time_is_set=False,
        target="1/4-2s", direction=0, is_bulb=False, synced_note="SYNCED 8s", battery=84,
    ),
    # Clouds want minutes, which is past what the camera will time itself. A
    # third of a stop of aperture is what gets it there, and the ISO stays at
    # base - which is where a several-minute exposure wants it.
    "main-bulb": MainScreen(
        mode="CLOUDS", iso="100", aperture="f/13", nd_label="8+1000", off_by="+0.1st", is_auto=True,
        selected="time", base_shutter="1/60 s", final_time="3m 28s",
        setting_time=False, shows_nudge_hint=True, time_is_set=False,
        target="2-6min", direction=0, is_bulb=True, synced_note="SYNCED 2m", battery=71,
    ),
    # Before the first SYNC there is no scene to work back from, and the device
    # says so rather than printing a recipe it cannot stand behind.
    "main-not-synced": MainScreen(
        mode="MANUAL", iso="--", aperture="--", nd_label="--", off_by="--", is_auto=True,
        selected="time", base_shutter="--", final_time="1.0 s",
        setting_time=False, shows_nudge_hint=True, time_is_set=False,
        target="", direction=0, is_bulb=False, synced_note="NOT SYNCED", battery=100,
    ),
    # An hour at noon, metered at 1/2000: every filter in the bag, stopped all
    # the way down, and it still lands most of a stop short - which the row says
    # out loud rather than quietly rounding.
    "main-stacked": MainScreen(
        mode="NO PEOPLE", iso="100", aperture="f/22", nd_label="8+64+1000", off_by="+0.9st", is_auto=True,
        selected="MODE", base_shutter="1/2000 s", final_time="1h",
        setting_time=False, shows_nudge_hint=True, time_is_set=False,
        target="2-8min", direction=-1, is_bulb=True, synced_note="SYNCED 30s", battery=66,
    ),
    # The same scene with one filter in the bag. The time asked for is still the
    # time on screen: a camera in shutter priority takes the shot too.
    "main-out-of-reach": MainScreen(
        mode="CLOUDS", iso="100", aperture="f/22", nd_label="8", off_by="+8.6st", is_auto=True,
        selected="time", base_shutter="1/60 s", final_time="3m 28s",
        setting_time=False, shows_nudge_hint=True, time_is_set=False,
        target="2-6min", direction=0, is_bulb=True, synced_note="SYNCED 12s", battery=58,
    ),
    # The settings taken over by hand. The device has stopped choosing: ISO and
    # aperture are the photographer's, the filters stay whatever is screwed on,
    # and the off row is the whole point - it is what says where that leaves you.
    "main-manual": MainScreen(
        mode="CLOUDS", iso="250", aperture="f/8", nd_label="8+1000", off_by="+2.3st",
        is_auto=False, selected="ISO", base_shutter="1/60 s", final_time="3m 28s",
        setting_time=False, shows_nudge_hint=True, time_is_set=False,
        target="2-6min", direction=0, is_bulb=True, synced_note="SYNCED 40s", battery=74,
    ),
    # A time dialled away from the scenario's own: SET is what says so.
    "main-time-set": MainScreen(
        mode="CLOUDS", iso="100", aperture="f/11", nd_label="8+1000", off_by="exact", is_auto=True,
        selected="time", base_shutter="1/60 s", final_time="2m 19s",
        setting_time=False, shows_nudge_hint=True, time_is_set=True,
        target="2-6min", direction=0, is_bulb=True, synced_note="SYNCED 30s", battery=78,
    ),
    # Mid-dial: left and right walk the time, up and down move a second, and the
    # clock face holds its shape while they do.
    "main-setting-time": MainScreen(
        mode="CLOUDS", iso="100", aperture="f/11", nd_label="8+1000", off_by="exact", is_auto=True,
        selected="time", base_shutter="1/60 s", final_time="02:19",
        setting_time=True, shows_nudge_hint=True, time_is_set=True,
        target="2-6min", direction=0, is_bulb=True, synced_note="SYNCED 30s", battery=78,
    ),
    # The fast end of the dial: waves want a shutter the camera times itself, and
    # the ladder reaches it - the same dial a self-timer would use.
    "main-setting-waves": MainScreen(
        mode="WAVES", iso="100", aperture="f/11", nd_label="8", off_by="-0.1st", is_auto=True,
        selected="time", base_shutter="1/60 s", final_time="1/8 s",
        setting_time=True, shows_nudge_hint=False, time_is_set=True,
        target="1/15-1/2s", direction=0, is_bulb=False, synced_note="SYNCED 4s", battery=82,
    ),
    # The delay between the press and the shutter, so the tripod stops ringing
    # before anything is recorded. Drawn once and left, which is why nothing on
    # it counts: the panel could not keep up with a number that did.
    "delay": DelayScreen(
        mode="CLOUDS", exposure="3m 28s", delay="8s", is_bulb=True, battery=62,
    ),
    # The numbers all come off the same ten-second step, so they agree with each
    # other: the elapsed and what is left add up to the total, and the bar is at
    # the elapsed rather than somewhere between two of them.
    # No UPS fitted, or the I2C bus never came up. The battery is hatched rather
    # than empty: one says the number is not known, the other says go home.
    "main-no-battery": MainScreen(
        mode="WATERFALL", iso="160", aperture="f/11", nd_label="64", off_by="+0.1st",
        is_auto=True, selected="MODE", base_shutter="1/60 s", final_time="0.7 s",
        setting_time=False, shows_nudge_hint=False, time_is_set=False,
        target="1/4-2s", direction=0, is_bulb=False, synced_note="SYNCED 20s", battery=None,
    ),
    # On the charger, at the level where the fill edge runs through the bolt -
    # the one case that decides how the bolt has to be drawn.
    "main-charging": MainScreen(
        mode="WATERFALL", iso="160", aperture="f/11", nd_label="64", off_by="+0.1st",
        is_auto=True, selected="MODE", base_shutter="1/60 s", final_time="0.7 s",
        setting_time=False, shows_nudge_hint=False, time_is_set=False,
        target="1/4-2s", direction=0, is_bulb=False, synced_note="SYNCED 20s", battery=50,
        charging=True,
    ),
    # The camera refused. The countdown is gone rather than running against a
    # shutter that never opened, and the bar says which kind of refusal it was.
    "main-no-camera": MainScreen(
        mode="CLOUDS", iso="--", aperture="--", nd_label="--", off_by="--",
        is_auto=True, selected="time", base_shutter="--", final_time="3m 28s",
        setting_time=False, shows_nudge_hint=True, time_is_set=False,
        target="2-6min", direction=0, is_bulb=True, synced_note="NO CAMERA", battery=64,
    ),
    "countdown-bulb": CountdownScreen(
        mode="CLOUDS", remaining="3:40", elapsed="1:20", total="5:00",
        progress=80 / 300, is_bulb=True, battery=62,
    ),
    "countdown-nearly-done": CountdownScreen(
        mode="Waterfall", remaining="0:10", elapsed="0:50", total="1:00",
        progress=50 / 60, is_bulb=False, battery=59,
    ),
    "settings-selected": MainScreen(
        mode="WAVES", iso="100", aperture="f/11", nd_label="8", off_by="-0.1st", is_auto=True,
        selected="settings", base_shutter="1/60 s", final_time="1/8 s",
        setting_time=False, shows_nudge_hint=False, time_is_set=True,
        target="1/15-1/2s", direction=0, is_bulb=False, synced_note="SYNCED 4s", battery=10,
    ),
    # The shape of the kit: the bag, how far the ISO may be pushed, and the two
    # ends of the lens the device is allowed to use.
    "settings": SettingsScreen(
        entries=(
            SettingsEntry("FILTERS", "9 owned"),
            SettingsEntry("ISO MAX", "400"),
            SettingsEntry("APER MIN", "f/4"),
            SettingsEntry("APER MAX", "f/16"),
            SettingsEntry("ABOUT", "v0.1"),
        ),
        selected=2, battery=10,
    ),
    "settings-filters": SettingsScreen(
        entries=tuple(SettingsEntry(f.name, TYPICAL_BAG.ownership_label(f)) for f in COMMON_FILTERS),
        selected=2, battery=10, title="FILTERS", left_right_change_values=False,
    ),
    "settings-filters-scrolled": SettingsScreen(
        entries=tuple(SettingsEntry(f.name, TYPICAL_BAG.ownership_label(f)) for f in COMMON_FILTERS),
        selected=8, battery=10, title="FILTERS", left_right_change_values=False,
    ),
}


RENDERERS = {
    SplashScreen: render_splash,
    DelayScreen: render_delay,
    SettingsScreen: render_settings,
    CountdownScreen: render_countdown,
    MainScreen: render_main,
}


def render(name, screen):
    return RENDERERS[type(screen)](screen)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, screen in CASES.items():
        frame = render(name, screen)
        frame.save(OUTPUT_DIR / f"{name}.png")

        readme_size = (frame.width * README_SCALE, frame.height * README_SCALE)
        frame.resize(readme_size, resample=0).save(OUTPUT_DIR / f"{name}@{README_SCALE}x.png")
        print(f"  {name}")

    from nd_timer.ui.panel import to_panel_bytes

    SPLASH_BUFFER.write_bytes(to_panel_bytes(render("splash", CASES["splash"])))
    print(f"  splash.bin ({SPLASH_BUFFER.stat().st_size} bytes)")

    print(f"\n{len(CASES)} screens written to {OUTPUT_DIR.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
