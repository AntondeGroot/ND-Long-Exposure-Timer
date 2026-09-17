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

from nd_timer.ui.screens import (  # noqa: E402
    CountdownScreen,
    MainScreen,
    SplashScreen,
    render_countdown,
    render_main,
    render_splash,
)

OUTPUT_DIR = REPO / "docs" / "screens"

# The splash is also written as a packed panel buffer, so the boot-time script can
# push it without importing Pillow - which costs seconds on an armv6 Pi, spent
# staring at a blank panel.
SPLASH_BUFFER = REPO / "assets" / "splash.bin"

# Upscaled copies for the README: 250x122 is unreadably small on a web page, and
# nearest-neighbour keeps the pixels honest rather than blurring them.
README_SCALE = 3

# One case per state worth documenting - and worth noticing a change to.
CASES = {
    "splash": SplashScreen(message="starting up...", version="v0.1"),
    "main-waterfall": MainScreen(
        mode="WATERFALL", iso="100", aperture="f/11", nd_label="64", nd_stops="6st",
        selected="APER", base_shutter="1/60 s", final_time="1.1 s",
        setting_time=False, shows_nudge_hint=True, time_is_set=False,
        target="1/4-2s", direction=0, is_bulb=False, synced_note="SYNCED 8s", battery=84,
    ),
    "main-bulb": MainScreen(
        mode="CLOUDS", iso="100", aperture="f/11", nd_label="8+1000", nd_stops="13st",
        selected="MODE", base_shutter="1/60 s", final_time="2m 17s",
        setting_time=False, shows_nudge_hint=True, time_is_set=False,
        target="2-6min", direction=0, is_bulb=True, synced_note="SYNCED 2m", battery=71,
    ),
    "main-not-synced": MainScreen(
        mode="MANUAL", iso="--", aperture="--", nd_label="none", nd_stops="0st",
        selected="ISO", base_shutter="--", final_time="--",
        setting_time=False, shows_nudge_hint=True, time_is_set=False,
        target="", direction=0, is_bulb=False, synced_note="NOT SYNCED", battery=100,
    ),
    "main-stacked": MainScreen(
        mode="CLOUDS", iso="200", aperture="f/16", nd_label="8+64+1000", nd_stops="19st",
        selected="ND", base_shutter="1/125 s", final_time="1h 10m",
        setting_time=False, shows_nudge_hint=True, time_is_set=False,
        target="2-6min", direction=-1, is_bulb=True, synced_note="SYNCED 30s", battery=66,
    ),
    # The answer taken over by hand: the filters ask for 17s, the photographer
    # wants 2m 19s, and SET is what stops the two contradicting each other.
    "main-time-set": MainScreen(
        mode="CLOUDS", iso="100", aperture="f/11", nd_label="1000", nd_stops="10st",
        selected="time", base_shutter="1/60 s", final_time="2m 19s",
        setting_time=False, shows_nudge_hint=True, time_is_set=True,
        target="2-6min", direction=0, is_bulb=True, synced_note="SYNCED 30s", battery=78,
    ),
    # Mid-dial: left and right walk the time, up and down move a second, and the
    # clock face holds its shape while they do.
    "main-setting-time": MainScreen(
        mode="CLOUDS", iso="100", aperture="f/11", nd_label="1000", nd_stops="10st",
        selected="time", base_shutter="1/60 s", final_time="02:19",
        setting_time=True, shows_nudge_hint=True, time_is_set=True,
        target="2-6min", direction=0, is_bulb=True, synced_note="SYNCED 30s", battery=78,
    ),
    # The fast end of the dial: waves want a shutter the camera times itself, and
    # the ladder reaches it - the same dial a self-timer would use.
    "main-setting-waves": MainScreen(
        mode="WAVES", iso="100", aperture="f/11", nd_label="8", nd_stops="3st",
        selected="time", base_shutter="1/60 s", final_time="1/8 s",
        setting_time=True, shows_nudge_hint=False, time_is_set=True,
        target="1/15-1/2s", direction=0, is_bulb=False, synced_note="SYNCED 1/60", battery=82,
    ),
    "countdown-bulb": CountdownScreen(
        mode="CLOUDS", remaining="3:42", elapsed="1:18", total="5:00",
        progress=0.26, is_bulb=True, battery=62,
    ),
    "countdown-nearly-done": CountdownScreen(
        mode="Waterfall", remaining="0:04", elapsed="0:56", total="1:00",
        progress=0.93, is_bulb=False, battery=59,
    ),
}


RENDERERS = {
    SplashScreen: render_splash,
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
