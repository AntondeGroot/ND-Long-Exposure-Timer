#!/usr/bin/env bash
#
# camera-probe.sh - find out what the camera looks like to gphoto2, from a Pi
# we cannot log into.
#
# The USB port cannot be a host (camera) and a peripheral (ssh) at once, so this
# runs unattended: install it, switch to host mode, and the Pi probes the camera
# on the next boot and writes everything to a log. usb-mode.sh's revert timer
# brings ssh back by itself, and the log is waiting.
#
# Usage (on the Pi):
#   sudo ./camera-probe.sh --install    install the boot job
#   sudo ./camera-probe.sh --run        probe right now (host mode required)
#   sudo ./camera-probe.sh --remove     uninstall the boot job
#          ./camera-probe.sh --show     print the last log

set -euo pipefail

LOG="/var/log/camera-probe.log"
UNIT="/etc/systemd/system/camera-probe.service"
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
ACTION=""

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Everything below this line assumes the Pi. Run on the Mac, these commands
# either do not exist or aim at the wrong machine - a reboot meant for the timer
# restarts the laptop - so refuse outright instead of half-running.
[[ "$(uname -s)" == "Linux" ]] || die "run this on the Pi, not here (this is $(uname -s))"

REVERT_WHEN_DONE=0
# Not "[[ ... ]] && VAR=1": as a bare statement that returns 1 when false, which
# set -e treats as a fatal error.
if [[ "${2:-}" == "--revert-when-done" ]]; then
  REVERT_WHEN_DONE=1
fi

case "${1:-}" in
  --install) ACTION=install ;;
  --run)     ACTION=run ;;
  --remove)  ACTION=remove ;;
  --show)    ACTION=show ;;
  *)         sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
esac

if [[ "$ACTION" == "show" ]]; then
  [[ -f "$LOG" ]] || die "no log yet at $LOG"
  cat "$LOG"
  exit 0
fi

[[ $EUID -eq 0 ]] || die "run with sudo"

# ---------------------------------------------------------------- the probe

run_probe() {
  exec > >(tee -a "$LOG") 2>&1

  echo
  echo "================================================================"
  echo "camera probe - $(date)"
  echo "================================================================"

  echo
  echo "--- usb topology ---"
  lsusb 2>&1 || echo "lsusb unavailable"

  echo
  echo "--- port role (host means the camera can work) ---"
  if [[ -d /sys/class/net/usb0 ]]; then
    echo "PERIPHERAL - the port is an ethernet gadget, so no camera will be seen."
    echo "Switch with: sudo usb-mode.sh host --reboot"
  else
    echo "host (no usb0 gadget interface)"
  fi

  echo
  echo "--- gphoto2 --auto-detect ---"
  timeout 30 gphoto2 --auto-detect 2>&1 || echo "(failed or timed out)"

  # Everything below is meaningless without a camera, and --abilities blocks
  # for a long time when there is none.
  if ! timeout 30 gphoto2 --auto-detect 2>/dev/null | tail -n +3 | grep -q .; then
    echo
    echo "NO CAMERA DETECTED."
    echo "Check: camera switched on, not asleep, set to PTP/MTP (not mass storage),"
    echo "and that the cable carries VBUS, D+, D- and GND."
    echo "=== probe finished $(date) ==="
    return 0
  fi

  echo
  echo "--- gphoto2 --summary ---"
  timeout 60 gphoto2 --summary 2>&1 || echo "(failed)"

  echo
  echo "--- gphoto2 --abilities ---"
  timeout 60 gphoto2 --abilities 2>&1 || echo "(failed)"

  # The point of the whole exercise: which config key drives a timed exposure.
  echo
  echo "--- exposure-related config keys ---"
  timeout 60 gphoto2 --list-config 2>/dev/null \
    | grep -iE 'bulb|shutterspeed|exposure|remoterelease|capturetarget|eosremote|manualfocus' \
    || echo "(none matched - full list below)"

  echo
  echo "--- full config list ---"
  timeout 60 gphoto2 --list-config 2>&1 || echo "(failed)"

  echo
  echo "=== probe finished $(date) ==="

  # Get straight back to a mode with ssh. Waiting out a revert timer means
  # sitting there wondering whether the probe has run yet; this is deterministic.
  if [[ $REVERT_WHEN_DONE -eq 1 && ! -d /sys/class/net/usb0 ]]; then
    local mode_script="${SELF%/*}/usb-mode.sh"
    if [[ -x "$mode_script" ]]; then
      echo "--- probe done, returning to peripheral mode and rebooting ---"
      "$mode_script" peripheral --reboot
    else
      echo "--- cannot self-revert: $mode_script not found ---"
    fi
  fi
}

case "$ACTION" in
  run)
    run_probe
    log "written to $LOG"
    ;;

  install)
    cat > "$UNIT" <<UNIT_EOF
[Unit]
Description=Probe the attached camera with gphoto2 and log the result
After=multi-user.target
Wants=multi-user.target

[Service]
Type=oneshot
RemainAfterExit=yes
# Give the camera a moment to finish enumerating after boot.
ExecStartPre=/bin/sleep 15
ExecStart=${SELF} --run --revert-when-done

[Install]
WantedBy=multi-user.target
UNIT_EOF
    systemctl daemon-reload
    systemctl enable camera-probe.service >/dev/null 2>&1
    log "installed - it will run on every boot until you --remove it"
    log "log: $LOG"
    echo
    echo "Now:  sudo usb-mode.sh host --reboot"
    echo "The Pi boots in host mode, probes the camera, then immediately flips"
    echo "back to peripheral and reboots - about two minutes, no waiting."
    echo "The revert timer stays armed underneath as a backstop."
    ;;

  remove)
    systemctl disable --now camera-probe.service >/dev/null 2>&1 || true
    rm -f "$UNIT"
    systemctl daemon-reload
    log "removed (the log is kept at $LOG)"
    ;;
esac
