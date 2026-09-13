#!/usr/bin/env bash
#
# enable-serial-console.sh - turn the Pi's USB port into a login console.
#
# Run on the Mac with the card in the reader. Swaps the ethernet gadget for the
# serial gadget and points a console at it, so the Pi offers a login prompt over
# the same USB cable:
#
#     screen /dev/cu.usbmodem* 115200
#
# This depends only on the kernel and getty - no NetworkManager, DHCP, link-local
# or mDNS - which is why it is the fallback when gadget networking will not come
# up. It also strips any leftover firstrun hooks, which is what breaks a Pi stuck
# rebooting into the setup target.
#
# Usage: ./enable-serial-console.sh [--revert]
#   --revert   go back to the ethernet gadget (g_ether, no serial console)

set -euo pipefail

REVERT=0
[[ "${1:-}" == "--revert" ]] && REVERT=1
[[ "${1:-}" =~ ^(-h|--help)$ ]] && { sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

BOOT=""
for candidate in /Volumes/bootfs /Volumes/boot; do
  [[ -d "$candidate" ]] && { BOOT="$candidate"; break; }
done
[[ -n "$BOOT" ]] || die "no boot partition mounted - put the card in the reader"

CMDLINE="$BOOT/cmdline.txt"
cp "$CMDLINE" "$CMDLINE.bak"

line="$(tr -d '\n' < "$CMDLINE")"

# Any surviving firstrun hook reboots the Pi straight back into the setup target,
# where no gadget driver is ever loaded. Always clear it.
if [[ "$line" == *systemd.run* ]]; then
  line="$(sed 's| systemd\.run=[^ ]*||g; s| systemd\.run_success_action=[^ ]*||g; s| systemd\.unit=[^ ]*||g' <<<"$line")"
  log "removed leftover firstrun hooks (this is what causes a reboot loop)"
fi

if [[ $REVERT -eq 1 ]]; then
  line="${line//modules-load=dwc2,g_serial/modules-load=dwc2,g_ether}"
  line="$(sed 's| console=ttyGS0,115200||g' <<<"$line")"
  log "reverted to the ethernet gadget"
else
  # Legacy gadget modules are mutually exclusive - only one can claim the UDC.
  if [[ "$line" == *modules-load=dwc2,g_ether* ]]; then
    line="${line//modules-load=dwc2,g_ether/modules-load=dwc2,g_serial}"
  elif [[ "$line" != *g_serial* ]]; then
    line="$line modules-load=dwc2,g_serial"
  fi
  # systemd starts a getty on every console= device, so this is what gives the
  # login prompt. Last one wins for /dev/console, so it goes at the end.
  [[ "$line" == *ttyGS0* ]] || line="$line console=ttyGS0,115200"
  log "switched to the serial gadget with a console on ttyGS0"
fi

printf '%s\n' "$line" > "$CMDLINE"
[[ "$(wc -l < "$CMDLINE")" -le 1 ]] || die "cmdline.txt must be one line - restore $CMDLINE.bak"

# The serial gadget needs peripheral mode just as the ethernet one did.
grep -q '^dtoverlay=dwc2,dr_mode=peripheral' "$BOOT/config.txt" \
  || warn "dtoverlay=dwc2,dr_mode=peripheral is missing from config.txt - the gadget will not enumerate"

log "cmdline.txt is now:"
sed 's/^/    /' "$CMDLINE"
sync

if [[ $REVERT -eq 0 ]]; then
cat <<'EOF'

Next:
  1. Eject the card, put it in the Pi, plug the USB cable into the inner port.
  2. Wait ~60 seconds, then find the device:
         ls /dev/cu.usbmodem*
  3. Connect:
         screen /dev/cu.usbmodem* 115200
     Press Enter if the screen looks blank - you should get a login prompt.
     Leave screen with: Ctrl-A then K, then y.

If no /dev/cu.usbmodem* appears, the Pi is not reaching userspace at all, which
is a different problem from the networking we have been chasing.
EOF
fi
