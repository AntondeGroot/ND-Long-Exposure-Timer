#!/usr/bin/env bash
#
# usb-mode.sh - switch the Pi Zero's USB port between the two things it cannot
# do at once: talking to the camera, and being reachable over USB.
#
#   peripheral   the port is an ethernet gadget - ssh over the cable works,
#                the camera does not (this is the development mode)
#   host         the port drives USB devices - gphoto2 sees the camera,
#                but the network link over USB is gone
#
# Switching to host mode cuts the only way in on a Pi with no wifi, so by default
# it arms an automatic revert: if you have not confirmed with "keep" within the
# timeout, the Pi switches back to peripheral and reboots, and ssh returns.
#
# Usage (run on the Pi):
#   sudo ./usb-mode.sh status
#   sudo ./usb-mode.sh host [--revert-after MINUTES] [--permanent] [--reboot]
#   sudo ./usb-mode.sh peripheral [--reboot]
#   sudo ./usb-mode.sh keep        # cancel a pending revert, host mode stays

set -euo pipefail

REVERT_MINUTES=15
PERMANENT=0
DO_REBOOT=0
ACTION=""

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REVERT_UNIT="usb-mode-revert"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

CONFIG="/boot/firmware/config.txt"
[[ -f "$CONFIG" ]] || CONFIG="/boot/config.txt"

while [[ $# -gt 0 ]]; do
  case "$1" in
    host|peripheral|status|keep) ACTION="$1" ;;
    --revert-after) REVERT_MINUTES="${2:?--revert-after needs minutes}"; shift ;;
    --permanent)    PERMANENT=1 ;;
    --reboot)       DO_REBOOT=1 ;;
    -h|--help)      sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)              die "unknown argument: $1" ;;
  esac
  shift
done

[[ -n "$ACTION" ]] || die "say what to do: status, host, peripheral or keep"
[[ -f "$CONFIG" ]] || die "no config.txt found - is this a Raspberry Pi?"

# config.txt is section-scoped, and the stock file ships a
# "dtoverlay=dwc2,dr_mode=host" under [cm5] that does NOT apply to a Zero. Only
# lines in [all] (or before any section header) count, so find that line number
# and work with it alone - never a blanket match across the file.
applicable_line() {
  awk '
    /^\[/   { section = $0; next }
    /^dtoverlay=dwc2,dr_mode=/ {
      if (section == "" || section == "[all]") line = NR
    }
    END { print line + 0 }
  ' "$CONFIG"
}

current_mode() {
  local n
  n="$(applicable_line)"
  [[ "$n" -gt 0 ]] || { echo unknown; return; }
  sed -n "${n}s|^dtoverlay=dwc2,dr_mode=||p" "$CONFIG" | tr -d '[:space:]'
}

# ---------------------------------------------------------------- status

if [[ "$ACTION" == "status" ]]; then
  echo "  configured mode : $(current_mode)   (takes effect at boot)"
  if [[ -d /sys/class/net/usb0 ]]; then
    echo "  running as      : peripheral (usb0 exists: $(ip -4 addr show usb0 2>/dev/null | awk '/inet /{print $2}'))"
  else
    echo "  running as      : host (no usb0 interface)"
  fi
  if systemctl is-enabled "${REVERT_UNIT}.timer" >/dev/null 2>&1; then
    echo "  pending revert  : ARMED - will return to peripheral and reboot"
    systemctl list-timers "${REVERT_UNIT}.timer" --no-pager 2>/dev/null | sed -n '2p' | sed 's/^/                    /'
  else
    echo "  pending revert  : none"
  fi
  command -v gphoto2 >/dev/null && echo "  camera          : $(gphoto2 --auto-detect 2>/dev/null | tail -n +3 | grep -c . ) detected"
  exit 0
fi

[[ $EUID -eq 0 ]] || die "run with sudo"

# ---------------------------------------------------------------- keep

if [[ "$ACTION" == "keep" ]]; then
  if systemctl is-enabled "${REVERT_UNIT}.timer" >/dev/null 2>&1; then
    systemctl disable --now "${REVERT_UNIT}.timer" >/dev/null 2>&1
    log "cancelled the pending revert - host mode stays until you change it"
  else
    log "nothing to cancel"
  fi
  exit 0
fi

# ---------------------------------------------------------------- switch

set_mode() {
  local mode="$1"
  local n
  cp "$CONFIG" "${CONFIG}.usb-mode.bak"
  n="$(applicable_line)"
  if [[ "$n" -gt 0 ]]; then
    # Rewrite that one line only, leaving the [cm5] line and everything else alone.
    sed -i "${n}s|.*|dtoverlay=dwc2,dr_mode=${mode}|" "$CONFIG"
    log "set line $n of $CONFIG to dr_mode=$mode"
  else
    printf '\n[all]\ndtoverlay=dwc2,dr_mode=%s\n' "$mode" >> "$CONFIG"
    log "appended dr_mode=$mode under [all] in $CONFIG"
  fi
  [[ "$(current_mode)" == "$mode" ]] || die "verification failed - restore ${CONFIG}.usb-mode.bak"
}

arm_revert() {
  local minutes="$1"
  cat > "/etc/systemd/system/${REVERT_UNIT}.service" <<UNIT_EOF
[Unit]
Description=Return the USB port to peripheral mode so ssh over USB works again

[Service]
Type=oneshot
ExecStart=${SELF} peripheral --reboot
UNIT_EOF

  cat > "/etc/systemd/system/${REVERT_UNIT}.timer" <<TIMER_EOF
[Unit]
Description=Deadline for confirming host mode

[Timer]
OnBootSec=${minutes}min
AccuracySec=10s
Unit=${REVERT_UNIT}.service

[Install]
WantedBy=timers.target
TIMER_EOF

  systemctl daemon-reload
  # Never report the safety net as armed without checking: a silently failed
  # enable here means host mode with no way back, which is the one outcome this
  # whole mechanism exists to prevent.
  if ! systemctl enable "${REVERT_UNIT}.timer" 2>&1 | sed 's/^/    /'; then
    die "could not enable ${REVERT_UNIT}.timer - refusing to switch to host mode without a way back"
  fi
  systemctl is-enabled "${REVERT_UNIT}.timer" >/dev/null 2>&1 \
    || die "${REVERT_UNIT}.timer is still not enabled - refusing to leave you stranded"
  log "armed automatic revert: ${minutes} minutes after the next boot (verified)"
}

case "$ACTION" in
  host)
    # Arm the revert BEFORE changing the mode, so a failure to arm leaves the Pi
    # in the mode that still has ssh rather than the one that does not.
    if [[ $PERMANENT -eq 0 ]]; then
      arm_revert "$REVERT_MINUTES"
    fi
    set_mode host
    if [[ $PERMANENT -eq 1 ]]; then
      systemctl disable --now "${REVERT_UNIT}.timer" >/dev/null 2>&1 || true
      warn "permanent host mode: ssh over USB will NOT come back on its own."
      warn "to undo it you need a keyboard and mini-HDMI, or the SD card in another machine."
    else
      echo
      warn "After the reboot you lose ssh over USB. If you can get to a console,"
      warn "run 'sudo $SELF keep' to stay in host mode."
      warn "Otherwise the Pi reverts and reboots by itself in ${REVERT_MINUTES} minutes."
    fi
    ;;
  peripheral)
    # The revert timer fires on every boot, not only after a switch to host, so
    # this must be a no-op when there is nothing to revert - otherwise the Pi
    # reboots itself every N minutes for no reason.
    if [[ "$(current_mode)" == "peripheral" ]]; then
      systemctl disable --now "${REVERT_UNIT}.timer" >/dev/null 2>&1 || true
      log "already in peripheral mode - nothing to do, not rebooting"
      exit 0
    fi
    set_mode peripheral
    systemctl disable --now "${REVERT_UNIT}.timer" >/dev/null 2>&1 || true
    log "ssh over USB returns after the reboot (10.55.0.1)"
    ;;
esac

if [[ $DO_REBOOT -eq 1 ]]; then
  log "rebooting"
  systemctl --no-block reboot
else
  log "reboot to apply: sudo reboot"
fi
