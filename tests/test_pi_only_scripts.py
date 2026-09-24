"""The scripts that only make sense on the Pi must refuse to run anywhere else.

A `sudo reboot` typed into the wrong terminal restarts the laptop instead of the
timer, and the two terminals look identical. These scripts are the ones that
reboot, mask units or rewrite config.txt, so the wrong machine has to be a
refusal rather than a half-finished run.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

PI_ONLY = [
    "usb-mode.sh",
    "speed-up-boot.sh",
    "install-boot-splash.sh",
    "bulb-test.sh",
    "camera-probe.sh",
]


@pytest.fixture
def pretending_to_be_macos(tmp_path):
    """A PATH whose `uname` answers Darwin, so this holds on the Pi and in CI."""
    fake_uname = tmp_path / "uname"
    fake_uname.write_text('#!/bin/sh\necho Darwin\n')
    fake_uname.chmod(0o755)
    return {"PATH": f"{tmp_path}:/usr/bin:/bin", "HOME": str(tmp_path)}


@pytest.mark.parametrize("script", PI_ONLY)
def test_it_refuses_to_run_on_a_mac_before_reading_its_arguments(
    script, pretending_to_be_macos
):
    # --remove and --restore are the destructive ones; no argument at all is how
    # the accident actually happens. All three have to stop at the same place.
    for args in ([], ["--remove"], ["--restore"]):
        result = subprocess.run(
            ["bash", str(SCRIPTS_DIR / script), *args],
            capture_output=True,
            text=True,
            env=pretending_to_be_macos,
        )
        assert result.returncode != 0, f"{script} {args} ran on a Mac"
        assert "run this on the Pi" in result.stderr, (
            f"{script} {args} stopped for some other reason: "
            f"{result.stdout}{result.stderr}"
        )
