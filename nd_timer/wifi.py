"""Whether the Pi boots with Wi-Fi, and switching that.

Off means `dtoverlay=disable-wifi` in config.txt: the firmware never powers the radio,
so nothing searches for a network out in the field and the battery lasts longer. It
only takes effect at boot, which is why switching it is a reboot.

config.txt is read rather than the choice remembered anywhere else, because it is what
the Pi actually boots with: the settings screen can then never say ON for a Pi that
started without a radio.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

DISABLE_WIFI = "dtoverlay=disable-wifi"
CONFIG = Path("/boot/firmware/config.txt")
# Root-owned and installed by setup-pi.sh: the one command the app may run as root.
# It writes or removes the line above, then reboots.
HELPER = "/usr/local/sbin/nd-timer-wifi"


def boots_with_wifi(config_text: str) -> bool:
    """False only when an active line - not a commented one - disables Wi-Fi."""
    return not any(line.strip() == DISABLE_WIFI for line in config_text.splitlines())


class WifiSwitch:
    """config.txt on the Pi, read for the state and changed through the helper."""

    def __init__(self, config: Path = CONFIG, run=subprocess.run) -> None:
        self._config = config
        self._run = run

    def is_on(self) -> bool:
        """On when config.txt cannot be read: that is what the firmware does without the line."""
        try:
            return boots_with_wifi(self._config.read_text())
        except OSError:
            return True

    def switch(self, on: bool) -> str | None:
        """Ask the helper to switch and reboot. Returns what went wrong, or None.

        On success it never returns in practice: the reboot stops this process.
        """
        result = self._run(["sudo", "-n", HELPER, "on" if on else "off"], capture_output=True, text=True)
        if result.returncode == 0:
            return None
        return f"WIFI: {(result.stderr or 'switch failed').strip()[:40]}"
