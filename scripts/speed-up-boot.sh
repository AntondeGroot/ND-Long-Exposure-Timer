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

# cloud-init is disabled with a flag file rather than by masking its five units -
# that is the supported way, and it survives a cloud-init package upgrade putting
# the units back.
CLOUD_INIT_FLAG="/etc/cloud/cloud-init.disabled"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Everything below this line assumes the Pi. Run on the Mac, these commands
# either do not exist or aim at the wrong machine - a reboot meant for the timer
# restarts the laptop - so refuse outright instead of half-running.
[[ "$(uname -s)" == "Linux" ]] || die "run this on the Pi, not here (this is $(uname -s))"

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

# Static units: no [Install] section, so they can only be masked.
#
# rpi-resize-swap-file spends 19s a boot sizing /var/swap - measured - and on
# this image nothing ever turns that file into swap: dphys-swapfile.service is
# not installed and swapon reports nothing. Nineteen seconds and 426MB of card
# for a file the kernel never reads. --restore unmasks it.
MASK_BY_DEFAULT=(
  rpi-resize-swap-file.service
)

# cloud-init exists to configure a machine from a cloud provider's metadata
# service. This is a camera timer. It still costs the better part of a minute:
# on a measured boot here, cloud-init-main took 19s and sysinit.target waited on
# cloud-init-network until 59s, so almost the whole userspace boot sat behind it.
#
# It is only safe to do this AFTER the first boot. Pi OS seeds it from the boot
# partition (DataSourceNoCloud, seed=file:///boot/firmware), which is part of how
# a freshly flashed card sets itself up - so flash-sd.sh must not do this, and
# setup-pi.sh, which runs later, can.
disable_cloud_init() {
  [[ -d /etc/cloud ]] || return 0
  # An explicit if, not "[[ -e ... ]] && return": under set -e that reads as an
  # early return but its exit status is the test's, which makes the function
  # look failed to a caller that checks.
  if [[ -e "$CLOUD_INIT_FLAG" ]]; then
    return 0
  fi
  touch "$CLOUD_INIT_FLAG"
  printf '    disabled cloud-init (%s)\n' "$CLOUD_INIT_FLAG"
}

# NetworkManager is the biggest single item on this device's critical path:
# measured at 21s, of which 12s was NM blocked behind a systemd daemon-reload
# that netplan triggers. And it manages nothing - usb0 is unmanaged by a conf.d
# drop-in and addressed by usb0-static.service with plain ip commands, lo is the
# kernel's, and resolv.conf is a static file.
#
# That is true of THIS device, not of Pis in general: on one with wifi, disabling
# NetworkManager removes networking and quite possibly your way back in. So the
# preconditions are checked rather than assumed, and it declines out loud.
network_manager_is_doing_nothing() {
  local wireless managed

  # Any wireless hardware at all, configured or not.
  if [[ -n "$(ls -d /sys/class/net/*/wireless 2>/dev/null)" ]] \
     || [[ -n "$(ls /sys/class/ieee80211 2>/dev/null)" ]]; then
    warn "wifi hardware present - leaving NetworkManager alone"
    return 1
  fi

  # Any device NM actually manages, loopback aside.
  if command -v nmcli >/dev/null 2>&1; then
    managed="$(nmcli -t -f DEVICE,STATE device status 2>/dev/null \
               | grep -v "^lo:" | grep -cv ":unmanaged$" || true)"
    if [[ "${managed:-0}" -gt 0 ]]; then
      warn "NetworkManager is managing $managed device(s) - leaving it alone"
      return 1
    fi
  fi

  # If something points resolv.conf at NM, DNS goes with it.
  if [[ -L /etc/resolv.conf ]] && readlink /etc/resolv.conf | grep -qi "NetworkManager"; then
    warn "resolv.conf is managed by NetworkManager - leaving it alone"
    return 1
  fi

  return 0
}

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

# A "static" unit has no [Install] section, so systemctl disable fails on it and
# does nothing - silently, which is worse. Masking is the only way to stop one.
# Recorded with a prefix so --restore knows to unmask rather than enable.
mask_units() {
  local unit
  for unit in "$@"; do
    systemctl list-unit-files "$unit" >/dev/null 2>&1 || continue
    [[ "$(systemctl is-enabled "$unit" 2>/dev/null)" == "masked" ]] && continue
    if systemctl mask "$unit" >/dev/null 2>&1; then
      echo "mask:$unit" >> "$STATE_FILE"
      printf '    masked %s\n' "$unit"
    fi
  done
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
    if [[ "$unit" == mask:* ]]; then
      unit="${unit#mask:}"
      systemctl unmask "$unit" >/dev/null 2>&1 && printf '    unmasked %s\n' "$unit"
    else
      systemctl enable "$unit" >/dev/null 2>&1 && printf '    enabled %s\n' "$unit"
    fi
  done < "$STATE_FILE"
  rm -f "$STATE_FILE"
  if [[ -e "$CLOUD_INIT_FLAG" ]]; then
    rm -f "$CLOUD_INIT_FLAG"
    printf '    enabled cloud-init\n'
  fi
  log "reboot to apply"
  exit 0
fi

measure
echo
log "disabling services this device has no use for"
mkdir -p "$(dirname "$STATE_FILE")"
disable_units "${SAFE_TO_DISABLE[@]}"
mask_units "${MASK_BY_DEFAULT[@]}"
disable_cloud_init

if network_manager_is_doing_nothing; then
  disable_units NetworkManager.service NetworkManager-dispatcher.service
fi

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
