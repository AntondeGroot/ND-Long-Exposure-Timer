#!/usr/bin/env bash
# Switch the Pi's Wi-Fi for the next boot, then reboot into it.
#
# Usage (on the Pi, as root - the app runs it through sudo):
#   nd-timer-wifi off    boot without Wi-Fi: the firmware never powers the radio
#   nd-timer-wifi on     boot with Wi-Fi again
#   NDT_NO_REBOOT=1 nd-timer-wifi off    change config.txt but do not reboot
#
# setup-pi.sh installs this as /usr/local/sbin/nd-timer-wifi, owned by root, and lets
# the app's user run exactly that through sudo. It is a copy rather than a link into
# the app's folder on purpose: that folder belongs to the app's user, and sudo on a
# file that user can edit would hand them root.
#
# Off is `dtoverlay=disable-wifi` in a block of its own at the end of config.txt,
# under [all]. Its own block, not setup-pi.sh's: re-running setup rewrites that one,
# and would quietly switch Wi-Fi back on.
#
# With Wi-Fi off there is no ssh: switch it back on from the device's settings first.

set -euo pipefail

die() { printf '[x] %s\n' "$*" >&2; exit 1; }

# A reboot meant for the timer would restart the laptop instead.
[[ "$(uname -s)" == "Linux" ]] || die "run this on the Pi, not here (this is $(uname -s))"

case "${1:-}" in
  on | off) WANTED="$1" ;;
  *) die "usage: nd-timer-wifi on|off" ;;
esac

[[ $EUID -eq 0 ]] || die "needs root: sudo nd-timer-wifi $WANTED"

CONFIG_TXT="/boot/firmware/config.txt"
[[ -f "$CONFIG_TXT" ]] || CONFIG_TXT="/boot/config.txt"
[[ -f "$CONFIG_TXT" ]] || die "cannot find config.txt in /boot or /boot/firmware"

BEGIN="# >>> nd-timer wifi >>>"
END="# <<< nd-timer wifi <<<"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# Drop the block, and any other active disable-wifi line, so "on" really is on.
sed -e "/^${BEGIN}$/,/^${END}$/d" -e '/^[[:space:]]*dtoverlay=disable-wifi[[:space:]]*$/d' "$CONFIG_TXT" > "$tmp"

if [[ "$WANTED" == off ]]; then
  {
    echo "$BEGIN"
    echo "# Written by nd-timer-wifi from the device's settings: WIFI OFF."
    echo "[all]"
    echo "dtoverlay=disable-wifi"
    echo "$END"
  } >> "$tmp"
fi

# Written in place rather than renamed over: /boot/firmware is FAT, where a rename
# is no safer, and in-place keeps the file's owner and mode.
cat "$tmp" > "$CONFIG_TXT"
sync

echo "Wi-Fi $WANTED from the next boot"
if [[ "${NDT_NO_REBOOT:-}" == 1 ]]; then
  exit 0
fi
systemctl reboot
