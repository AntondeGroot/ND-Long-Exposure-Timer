#!/usr/bin/env bash
#
# speed-up-boot.sh - stop the Pi waiting for things this device does not have.
#
# The camera timer is switched on in the field and wanted immediately, so boot
# time is a feature. Most of what a stock Raspberry Pi OS waits for is irrelevant
# here: there is no wifi, no Bluetooth radio on a plain Zero, no modem, and the
# only "network" is a USB cable to a laptop that is usually not attached.
#
# Everything here is reversible, and the script prints how. Nothing that could
# cost you access to the device is disabled by default.
#
# Usage (on the Pi):
#   sudo ./speed-up-boot.sh --measure     just report, change nothing
#   sudo ./speed-up-boot.sh               disable the safe set
#   sudo ./speed-up-boot.sh --aggressive  also drop avahi and swap
#   sudo ./speed-up-boot.sh --restore     re-enable everything it disabled

set -euo pipefail

STATE_FILE="/var/lib/nd-timer-boot-disabled"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Waiting for a network that is a USB cable to a laptop is the classic Pi boot
# delay - these can each cost 15-30s and buy this device nothing.
SAFE_TO_DISABLE=(
  NetworkManager-wait-online.service
  systemd-networkd-wait-online.service
  # A plain Zero has no Bluetooth radio at all.
  bluetooth.service
  hciuart.service
  # No modem, no cellular anything.
  ModemManager.service
  # A hotkey daemon for input devices we drive ourselves through gpiozero.
  triggerhappy.service
  triggerhappy.socket
)

# Useful but not free. avahi is what answers raspberrypi.local, and the device
# has a static address, but losing it removes a way back in if that ever breaks.
AGGRESSIVE_EXTRAS=(
  avahi-daemon.service
  avahi-daemon.socket
  dphys-swapfile.service
)

measure() {
  log "boot time"
  systemd-analyze 2>/dev/null | sed 's/^/    /' || warn "systemd-analyze unavailable"
  echo
  log "slowest units"
  systemd-analyze blame 2>/dev/null | head -15 | sed 's/^/    /' || true
  echo
  log "critical chain"
  systemd-analyze critical-chain 2>/dev/null | head -12 | sed 's/^/    /' || true
}

disable_units() {
  local unit
  for unit in "$@"; do
    if ! systemctl list-unit-files "$unit" >/dev/null 2>&1; then
      continue
    fi
    if [[ "$(systemctl is-enabled "$unit" 2>/dev/null)" == "masked" ]]; then
      continue
    fi
    if systemctl disable --now "$unit" >/dev/null 2>&1; then
      echo "$unit" >> "$STATE_FILE"
      printf '    disabled %s\n' "$unit"
    fi
  done
}

[[ "${1:-}" == "--measure" ]] && { measure; exit 0; }
[[ $EUID -eq 0 ]] || die "run with sudo"

if [[ "${1:-}" == "--restore" ]]; then
  [[ -f "$STATE_FILE" ]] || die "nothing recorded as disabled"
  log "re-enabling what this script disabled"
  while read -r unit; do
    [[ -n "$unit" ]] || continue
    systemctl enable "$unit" >/dev/null 2>&1 && printf '    enabled %s\n' "$unit"
  done < "$STATE_FILE"
  rm -f "$STATE_FILE"
  log "reboot to apply"
  exit 0
fi

measure
echo
log "disabling services this device has no use for"
mkdir -p "$(dirname "$STATE_FILE")"
disable_units "${SAFE_TO_DISABLE[@]}"

if [[ "${1:-}" == "--aggressive" ]]; then
  warn "also dropping avahi (no more .local name) and swap"
  disable_units "${AGGRESSIVE_EXTRAS[@]}"
fi

# The bootloader's own pause, before Linux starts at all.
CONFIG="/boot/firmware/config.txt"
[[ -f "$CONFIG" ]] || CONFIG="/boot/config.txt"
if [[ -f "$CONFIG" ]] && ! grep -q '^boot_delay=0' "$CONFIG"; then
  printf '\n# No reason to pause before starting the kernel.\nboot_delay=0\n' >> "$CONFIG"
  log "set boot_delay=0 in $CONFIG"
fi

cat <<EOF

Done. Reboot, then compare:

    sudo systemctl reboot
    ./speed-up-boot.sh --measure

To put everything back:  sudo $0 --restore
EOF
