#!/usr/bin/env bash
#
# enable-gadget-network.sh - make an already-flashed card bring up its USB
# ethernet gadget, and configure this Mac's end of the link.
#
# The gadget enumerates fine out of the box, but Bookworm never configures usb0,
# so the link has no carrier and no address. This installs a one-shot boot script
# on the card that gives usb0 a static address, then points the Mac's end at the
# other half of the same subnet.
#
# Usage: ./enable-gadget-network.sh              # card inserted, Pi powered off
#        ./enable-gadget-network.sh --mac-only   # just configure this Mac
#        ./enable-gadget-network.sh --card-only  # just patch the card

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PI_IP="10.55.0.1"
MAC_IP="10.55.0.2"
NETMASK="255.255.255.0"
SERVICE_NAME="Raspberry Pi USB Gadget"
FIRSTRUN="gadget-network-firstrun.sh"

DO_CARD=1
DO_MAC=1

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mac-only)  DO_CARD=0 ;;
    --card-only) DO_MAC=0 ;;
    -h|--help)   sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)           die "unknown option: $1" ;;
  esac
  shift
done

# ---------------------------------------------------------------- the card

if [[ $DO_CARD -eq 1 ]]; then
  BOOT=""
  for candidate in /Volumes/bootfs /Volumes/boot; do
    [[ -d "$candidate" ]] && { BOOT="$candidate"; break; }
  done
  [[ -n "$BOOT" ]] || die "no boot partition mounted - put the card in the reader first (--mac-only to skip)"

  [[ -f "$SCRIPT_DIR/$FIRSTRUN" ]] || die "missing $SCRIPT_DIR/$FIRSTRUN"

  log "installing $FIRSTRUN on $BOOT"
  cp "$SCRIPT_DIR/$FIRSTRUN" "$BOOT/$FIRSTRUN"
  chmod +x "$BOOT/$FIRSTRUN"

  # systemd.run hijacks the first boot to run our script, then reboots into the
  # real system. The script deletes these parameters once it has done its work.
  if grep -q 'systemd.run=' "$BOOT/cmdline.txt"; then
    log "boot hook already present in cmdline.txt"
  else
    cp "$BOOT/cmdline.txt" "$BOOT/cmdline.txt.bak"
    # /boot/firmware is where Bookworm mounts this partition on the Pi.
    printf '%s systemd.run=/boot/firmware/%s systemd.run_success_action=reboot systemd.unit=kernel-command-line.target\n' \
      "$(tr -d '\n' < "$BOOT/cmdline.txt.bak")" "$FIRSTRUN" > "$BOOT/cmdline.txt"
    log "added the boot hook to cmdline.txt"
  fi

  [[ "$(wc -l < "$BOOT/cmdline.txt")" -le 1 ]] || die "cmdline.txt must be a single line - restore $BOOT/cmdline.txt.bak"

  log "cmdline.txt is now:"
  sed 's/^/    /' "$BOOT/cmdline.txt"

  sync
  log "card ready - eject it, put it in the Pi, and power it up"
  log "the Pi will boot, configure usb0, reboot once, and come up at $PI_IP"
fi

# ---------------------------------------------------------------- this Mac

if [[ $DO_MAC -eq 1 ]]; then
  if ! networksetup -listallnetworkservices 2>/dev/null | grep -qx "$SERVICE_NAME"; then
    warn "no '$SERVICE_NAME' network service - plug the Pi in and rerun with --mac-only"
  else
    log "setting '$SERVICE_NAME' to $MAC_IP (needs your password)"
    sudo networksetup -setmanual "$SERVICE_NAME" "$MAC_IP" "$NETMASK"
    log "this Mac is $MAC_IP, the Pi will be $PI_IP"
  fi
fi

cat <<EOF

Once the Pi has booted twice (give it ~3 minutes the first time):

    ping -c3 $PI_IP
    ssh <user>@$PI_IP

The Pi writes a log of what it did to the boot partition, so if it does not come
up, put the card back in the reader and read: /Volumes/bootfs/gadget-setup.log

To undo the Mac side:  sudo networksetup -setdhcp "$SERVICE_NAME"
EOF
