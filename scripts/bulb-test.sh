#!/usr/bin/env bash
#
# bulb-test.sh - prove the camera actually takes the exposure we ask for.
#
# /main/actions/bulb existing in the config list only means libgphoto2 offers
# the knob. This turns it and checks a file of roughly the right exposure landed
# on the card, which is the thing the timer depends on.
#
# Runs on the Pi in HOST mode, with the camera connected, in M mode with the
# shutter set to Bulb. Like camera-probe.sh it can run at boot and return the
# Pi to peripheral mode afterwards, so no console is needed.
#
# Usage (on the Pi, host mode):
#   sudo ./bulb-test.sh --run [SECONDS]           default 10
#   sudo ./bulb-test.sh --install [SECONDS]       run once at next boot, then revert
#   sudo ./bulb-test.sh --remove
#          ./bulb-test.sh --show

set -euo pipefail

LOG="/var/log/bulb-test.log"
UNIT="/etc/systemd/system/bulb-test.service"
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
SECONDS_DEFAULT=10
ACTION="${1:-}"
EXPOSURE="${2:-$SECONDS_DEFAULT}"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

# In host mode there is no network and no screen, so the activity LED is the only
# way to see what the Pi is doing. setup-pi.sh sets act_led_trigger=none, which
# frees it for exactly this. Failures here never matter - it is only an indicator.
LED=""
for candidate in /sys/class/leds/ACT /sys/class/leds/led0; do
  [[ -w "$candidate/brightness" ]] && { LED="$candidate/brightness"; break; }
done
led_on()  { [[ -n "$LED" ]] && echo 1 > "$LED" 2>/dev/null || true; }
led_off() { [[ -n "$LED" ]] && echo 0 > "$LED" 2>/dev/null || true; }
led_blink() {
  local n="${1:-3}"
  for ((i = 0; i < n; i++)); do led_on; sleep 0.2; led_off; sleep 0.2; done
}
die() { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Everything below this line assumes the Pi. Run on the Mac, these commands
# either do not exist or aim at the wrong machine - a reboot meant for the timer
# restarts the laptop - so refuse outright instead of half-running.
[[ "$(uname -s)" == "Linux" ]] || die "run this on the Pi, not here (this is $(uname -s))"

[[ "$EXPOSURE" =~ ^[0-9]+$ ]] || die "exposure must be a whole number of seconds"

case "$ACTION" in
  --show)
    [[ -f "$LOG" ]] || die "no log yet at $LOG"
    cat "$LOG"; exit 0 ;;
  --run|--install|--remove) ;;
  *) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
esac

[[ $EUID -eq 0 ]] || die "run with sudo"

run_test() {
  exec > >(tee -a "$LOG") 2>&1
  echo
  echo "================================================================"
  echo "bulb test - ${EXPOSURE}s - $(date)"
  echo "================================================================"

  if [[ -d /sys/class/net/usb0 ]]; then
    echo "PERIPHERAL mode - no camera can be attached. Nothing to do."
    echo "Switch with: sudo usb-mode.sh host --reboot"
    return 0
  fi

  if ! timeout 30 gphoto2 --auto-detect 2>/dev/null | tail -n +3 | grep -q .; then
    echo "NO CAMERA DETECTED - is it on, awake, and connected?"
    led_blink 10   # a long stutter means "no camera", not "still working"
    return 0
  fi
  echo "camera: $(gphoto2 --auto-detect 2>/dev/null | sed -n 3p)"

  # Write to the card, not to the Pi: the timer is not a tethered capture tool,
  # and a RAW file over USB 1.1 would take longer than the exposure.

  echo
  echo "--- shutter speed before ---"
  timeout 30 gphoto2 --get-config shutterspeed 2>&1 | grep -E '^Current|^Label' || true

  # Bulb only means anything when the camera is in M with the dial on Bulb; if it
  # is not, say so rather than producing a mystery 1/60th.
  # A leftover capture from a previous run would be mistaken for this run's frame.
  find / -maxdepth 2 \( -name 'capt*.nef' -o -name 'capt*.jpg' \) -delete 2>/dev/null || true

  local before after
  before="$(timeout 60 gphoto2 --list-files -R 2>/dev/null | grep -c '^#' || true)"
  before="${before:-0}"
  echo "files on card before: $before"

  echo
  echo "--- opening shutter for ${EXPOSURE}s (single gphoto2 session) ---"
  # This MUST be one invocation. Each gphoto2 process opens a PTP session and
  # closes it on exit, so "--set-config bulb=1" in its own process opens the
  # shutter and then tears down the session underneath it - the camera stops
  # answering and the next process cannot even detect it. Chaining the actions
  # with --wait-event keeps one session open across the whole exposure.
  local t0 t1 elapsed
  t0="$(date +%s.%N)"
  # capturetarget belongs in THIS invocation too: it is a gphoto2 session setting,
  # not something the camera remembers, so setting it in its own process has no
  # effect on the capture. =1 keeps the image on the camera's card instead of
  # routing ~20MB per frame through the Pi.
  timeout "$((EXPOSURE + 60))" gphoto2 \
      --set-config capturetarget=1 \
      --set-config bulb=1 \
      --wait-event="${EXPOSURE}s" \
      --set-config bulb=0 \
      --wait-event=3s 2>&1 || echo "(gphoto2 returned non-zero)"
  t1="$(date +%s.%N)"
  led_off
  elapsed="$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.2f", b-a}')"
  echo "sequence took ${elapsed}s (exposure asked for: ${EXPOSURE}s)"

  echo
  echo "--- is the camera still there? ---"
  timeout 30 gphoto2 --auto-detect 2>&1 | tail -n +3 | grep -q . \
    && echo "yes - session survived" \
    || echo "NO - the camera dropped off the bus"

  echo
  echo "--- kernel USB events (last 15) ---"
  dmesg 2>/dev/null | grep -iE "usb|nikon" | tail -15 || echo "(dmesg unavailable)"

  # The camera needs a moment to finish writing before the new file shows up.
  sleep 2

  after="$(timeout 60 gphoto2 --list-files -R 2>/dev/null | grep -c '^#' || true)"
  after="${after:-0}"
  echo "files on card after:  $after"

  # A frame captured to the camera's SDRAM and downloaded here is just as real as
  # one written to the card, so count both rather than calling a good shot a failure.
  local downloaded
  downloaded="$(find / -maxdepth 2 -name 'capt*.nef' -o -maxdepth 2 -name 'capt*.jpg' 2>/dev/null | head -1)"

  if [[ "$after" -gt "$before" ]]; then
    echo "RESULT: SUCCESS - $((after - before)) new file(s) on the camera card"
    timeout 60 gphoto2 --list-files -R 2>/dev/null | tail -3
  elif [[ -n "$downloaded" ]]; then
    echo "RESULT: SUCCESS (but downloaded, not kept on the card): $downloaded"
    echo "  capturetarget did not take effect - the frame went via the Pi."
  else
    echo "RESULT: NO NEW FILE - the shutter command returned but nothing was recorded."
    echo "Check the camera is in M mode with the shutter speed set to Bulb,"
    echo "and that it is not refusing to fire (autofocus unable to lock, card full)."
  fi

  # Whatever landed, report what the camera itself recorded - the only
  # trustworthy measure of the exposure.
  if [[ -n "$downloaded" ]] && command -v exiftool >/dev/null; then
    echo
    echo "--- exposure as recorded by the camera ---"
    exiftool -ExposureTime -ISO -FNumber -CreateDate "$downloaded" 2>/dev/null | sed 's/^/  /'
  fi

  echo "=== bulb test finished $(date) ==="
  led_blink 3
}

case "$ACTION" in
  run|--run)
    run_test
    log "written to $LOG"
    ;;

  --install)
    cat > "$UNIT" <<UNIT_EOF
[Unit]
Description=One-shot bulb exposure test, then return to peripheral mode
After=multi-user.target
Wants=multi-user.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=/bin/sleep 8
ExecStart=${SELF} --run ${EXPOSURE}
# Disable itself so it runs exactly once, then hand the port back to ssh.
ExecStartPost=/bin/systemctl disable bulb-test.service
ExecStartPost=${SELF%/*}/usb-mode.sh peripheral --reboot

[Install]
WantedBy=multi-user.target
UNIT_EOF
    systemctl daemon-reload
    systemctl enable bulb-test.service 2>&1 | sed 's/^/    /'
    systemctl is-enabled bulb-test.service >/dev/null 2>&1 \
      || die "could not enable bulb-test.service"
    log "installed: ${EXPOSURE}s exposure at next boot, then back to peripheral"
    echo
    echo "Now:  sudo usb-mode.sh host --reboot"
    ;;

  --remove)
    systemctl disable --now bulb-test.service >/dev/null 2>&1 || true
    rm -f "$UNIT"
    systemctl daemon-reload
    log "removed (log kept at $LOG)"
    ;;
esac
