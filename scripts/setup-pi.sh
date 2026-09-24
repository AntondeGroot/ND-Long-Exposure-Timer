#!/usr/bin/env bash
#
# setup-pi.sh - provision a Raspberry Pi Zero for the ND Long Exposure Timer.
#
# Sets up everything the hardware in the BOM needs:
#   - SPI enabled for the 2.13" e-paper display
#   - GPIO/Python stack (gpiozero, spidev, Pillow) in a venv
#   - Waveshare e-Paper driver library
#   - gphoto2 for camera control (delegates to install-gphoto2.sh)
#   - the boot splash (delegates to install-boot-splash.sh)
#   - a faster boot (delegates to speed-up-boot.sh)
#   - optional clean-shutdown GPIO pin (momentary buttons only, see --shutdown-pin)
#   - battery-friendly tweaks (activity LED off, splash off)
#   - a systemd unit so the timer starts on boot
#
# Safe to re-run: config.txt edits live in a marked block that gets replaced.
#
# Usage: sudo ./setup-pi.sh [options]
#   --user NAME        account that runs the timer (default: $SUDO_USER)
#   --app-dir PATH     project checkout (default: parent of this script)
#   --shutdown-pin N   install gpio-shutdown on BCM pin N. Only for a MOMENTARY
#                      button. A latching switch that cuts power cannot use this:
#                      the OS gets no warning, so there is nothing to halt.
#   --no-gphoto2       skip the camera stack
#   --no-splash        skip the boot splash service
#   --no-boot-speedup  leave the stock boot services alone
#   --no-power-tweaks  leave config.txt power settings alone
#   -y, --yes          no prompts
#
# Targets the plain Pi Zero (no wifi/Bluetooth). Headless access comes from USB
# gadget mode, set up at flash time by flash-sd.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TARGET_USER="${SUDO_USER:-${USER:-pi}}"
APP_DIR="$(dirname "$SCRIPT_DIR")"
SHUTDOWN_PIN=""
DO_GPHOTO2=1
DO_SPLASH=1
DO_BOOT_SPEEDUP=1
DO_POWER_TWEAKS=1
ASSUME_YES=0

SERVICE_NAME="nd-timer"
WAVESHARE_DIR="/opt/waveshare-epaper"
MARKER_BEGIN="# >>> ND Long Exposure Timer >>>"
MARKER_END="# <<< ND Long Exposure Timer <<<"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

usage() { sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)             TARGET_USER="${2:?--user needs a name}"; shift ;;
    --app-dir)          APP_DIR="${2:?--app-dir needs a path}"; shift ;;
    --shutdown-pin)     SHUTDOWN_PIN="${2:?--shutdown-pin needs a BCM pin}"; shift ;;
    --no-gphoto2)       DO_GPHOTO2=0 ;;
    --no-splash)        DO_SPLASH=0 ;;
    --no-boot-speedup)  DO_BOOT_SPEEDUP=0 ;;
    --no-power-tweaks)  DO_POWER_TWEAKS=0 ;;
    -y|--yes)           ASSUME_YES=1 ;;
    -h|--help)          usage ;;
    *)                  die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

confirm() {
  [[ $ASSUME_YES -eq 1 ]] && return 0
  read -r -p "$1 [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

as_user() { sudo -u "$TARGET_USER" -H "$@"; }

# ---------------------------------------------------------------- sanity checks

[[ $EUID -eq 0 ]] || die "run me with sudo: sudo $0 $*"
id "$TARGET_USER" >/dev/null 2>&1 || die "no such user: $TARGET_USER"
[[ -d "$APP_DIR" ]] || die "app dir does not exist: $APP_DIR"

if [[ ! -f /etc/rpi-issue ]] && ! grep -qi raspberry /proc/device-tree/model 2>/dev/null; then
  warn "this does not look like a Raspberry Pi. Nothing here will work as intended."
  confirm "continue anyway?" || die "aborted"
fi

# Bookworm moved the firmware config; older releases keep it in /boot.
CONFIG_TXT="/boot/firmware/config.txt"
[[ -f "$CONFIG_TXT" ]] || CONFIG_TXT="/boot/config.txt"
[[ -f "$CONFIG_TXT" ]] || die "cannot find config.txt in /boot or /boot/firmware"

MODEL="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo unknown)"
log "model: $MODEL"
log "user: $TARGET_USER   app dir: $APP_DIR   config: $CONFIG_TXT"

# ---------------------------------------------------------------- system packages

export DEBIAN_FRONTEND=noninteractive

# The Pi has no network of its own: everything here comes down a USB gadget link
# that is NATed by a laptop, and that link stutters. Apt's default is to give up
# on a stalled item and then thrash, which floods the screen with
#   W: Tried to start delayed item ... but failed
# and can end with packages missing. Retry rather than fail, ask for one file at
# a time instead of pipelining several, and allow a slow mirror longer than the
# default before calling it dead.
APT_OPTS=(
  -o Acquire::Retries=5
  -o Acquire::http::Pipeline-Depth=0
  -o Acquire::http::Timeout=60
  -o Acquire::ftp::Timeout=60
)

log "updating package lists"
apt-get "${APT_OPTS[@]}" update

log "installing base packages"
apt-get "${APT_OPTS[@]}" install -y \
  git curl ca-certificates \
  python3 python3-venv python3-pip python3-dev \
  python3-pil python3-numpy python3-spidev python3-gpiozero \
  python3-libgpiod libopenjp2-7 libtiff6 fonts-dejavu-core \
  raspi-config

# lgpio is the gpiozero backend that works on current Pi OS; on older releases
# it does not exist and RPi.GPIO is the right pin factory instead.
apt-get "${APT_OPTS[@]}" install -y python3-lgpio || apt-get "${APT_OPTS[@]}" install -y python3-rpi.gpio || \
  warn "no GPIO backend package found; pip will have to provide one"

# ---------------------------------------------------------------- interfaces

log "enabling SPI for the e-paper display"
raspi-config nonint do_spi 0

log "adding $TARGET_USER to hardware groups"
for grp in gpio spi i2c dialout video plugdev; do
  groupadd -f "$grp"
  usermod -aG "$grp" "$TARGET_USER"
done

# ---------------------------------------------------------------- config.txt

write_config_block() {
  local tmp
  tmp="$(mktemp)"

  # Drop any previous block, then append a fresh one.
  sed "/^${MARKER_BEGIN}$/,/^${MARKER_END}$/d" "$CONFIG_TXT" > "$tmp"

  {
    echo "$MARKER_BEGIN"
    echo "# Managed by scripts/setup-pi.sh - edits inside this block are overwritten."
    echo "dtparam=spi=on"
    echo ""
    echo "# The UPS HAT's fuel gauge is on I2C. Without this there is no bus for"
    echo "# it to answer on, and the battery reading has nowhere to come from."
    echo "dtparam=i2c_arm=on"
    if [[ -n "$SHUTDOWN_PIN" ]]; then
      echo ""
      echo "# Momentary button: pulling BCM${SHUTDOWN_PIN} to ground halts the Pi cleanly."
      echo "# GPIO3 doubles as a wake-from-halt pin, which is why it is the usual choice."
      echo "dtoverlay=gpio-shutdown,gpio_pin=${SHUTDOWN_PIN},active_low=1,gpio_pull=up"
    fi

    if [[ $DO_POWER_TWEAKS -eq 1 ]]; then
      echo ""
      echo "# Battery savers for the UPS HAT's cell. On a Zero the ACT LED is active-low,"
      echo "# so activelow=on is what switches it OFF - the Pi 3/4 recipe (=off)"
      echo "# leaves it permanently lit, which costs current instead of saving it."
      echo "# Note this also detaches the LED from SD activity, so it stops being"
      echo "# usable as a boot/disk-activity indicator while debugging."
      echo "dtparam=act_led_trigger=none"
      echo "dtparam=act_led_activelow=on"
      echo "disable_splash=1"
    fi

    echo "$MARKER_END"
  } >> "$tmp"

  install -m 0755 "$CONFIG_TXT" "${CONFIG_TXT}.nd-timer.bak"
  install -m 0755 "$tmp" "$CONFIG_TXT"
  rm -f "$tmp"
}

log "writing the managed block in $CONFIG_TXT (backup: ${CONFIG_TXT}.nd-timer.bak)"
write_config_block

# dtparam=i2c_arm=on turns the controller on; /dev/i2c-1 only appears once
# i2c-dev is loaded on top of it, and nothing loads that by itself - Pi OS
# leaves it to raspi-config, which nobody runs on a headless card. Without it
# the bus is enabled and unreachable, which looks exactly like a HAT that is
# not answering.
log "loading i2c-dev, now and at every boot"
echo "i2c-dev" > /etc/modules-load.d/nd-timer.conf
modprobe i2c-dev 2>/dev/null || warn "could not load i2c-dev now; it will load at the next boot"

# ---------------------------------------------------------------- python env

VENV_DIR="$APP_DIR/.venv"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  log "creating venv at $VENV_DIR (with system site packages for the GPIO bindings)"
  as_user python3 -m venv --system-site-packages "$VENV_DIR"
else
  log "reusing existing venv at $VENV_DIR"
fi

log "installing Python dependencies"
as_user "$VENV_DIR/bin/pip" install --upgrade pip wheel

if [[ -f "$APP_DIR/requirements.txt" ]]; then
  as_user "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"
else
  warn "no requirements.txt yet; installing the baseline the hardware needs"
  as_user "$VENV_DIR/bin/pip" install pillow gpiozero spidev
fi

# ---------------------------------------------------------------- e-paper driver

# Waveshare ship the 2.13" driver as a library in their e-Paper repo rather than
# on PyPI, so it gets cloned and pip-installed from the checkout.
if [[ -d "$WAVESHARE_DIR/.git" ]]; then
  log "updating the Waveshare e-Paper library"
  git -C "$WAVESHARE_DIR" pull --ff-only || warn "could not update; using the existing checkout"
else
  log "fetching the Waveshare e-Paper library"
  git clone --depth 1 https://github.com/waveshareteam/e-Paper.git "$WAVESHARE_DIR" \
    || warn "clone failed (no network?); install the display driver yourself later"
fi

EPD_PKG="$WAVESHARE_DIR/RaspberryPi_JetsonNano/python"
if [[ -d "$EPD_PKG" ]]; then
  # The package has a legacy setup.py and no pyproject.toml, so pip builds it in
  # place and needs to write egg-info into the source tree. pip runs as the target
  # user (to keep the venv out of root's hands), so the root-owned clone has to be
  # handed over first.
  chown -R "$TARGET_USER" "$WAVESHARE_DIR"
  as_user "$VENV_DIR/bin/pip" install "$EPD_PKG" \
    || warn "could not install the waveshare_epd package from $EPD_PKG"
else
  warn "Waveshare python library not found at $EPD_PKG"
fi

# ---------------------------------------------------------------- gphoto2

if [[ $DO_GPHOTO2 -eq 1 ]]; then
  if [[ -x "$SCRIPT_DIR/install-gphoto2.sh" ]]; then
    log "handing off to install-gphoto2.sh"
    "$SCRIPT_DIR/install-gphoto2.sh" --user "$TARGET_USER" $([[ $ASSUME_YES -eq 1 ]] && echo -y)
  else
    warn "install-gphoto2.sh not found next to this script; skipping the camera stack"
  fi
fi

# ----------------------------------------------------------- boot splash

# A Pi Zero takes most of a minute to reach the application. Without this the
# panel is blank for that whole time, which reads as a device that did not
# switch on - so it belongs in provisioning rather than in a command someone has
# to remember to type after every reflash.
if [[ $DO_SPLASH -eq 1 ]]; then
  if [[ -x "$SCRIPT_DIR/install-boot-splash.sh" ]]; then
    log "handing off to install-boot-splash.sh"
    "$SCRIPT_DIR/install-boot-splash.sh" --user "$TARGET_USER"
  else
    warn "install-boot-splash.sh not found next to this script; no splash on boot"
  fi
fi

# ------------------------------------------------------------- boot speed

# Measured on a stock card here: 1m44s to a login, with sysinit.target waiting
# on cloud-init until 59s and NetworkManager taking another 21s on the critical
# path. The device is switched on in the field and wanted immediately, so that
# is not a detail - it is most of the time the panel sits blank, and most of the
# wait before ssh answers.
#
# Only the safe set. --aggressive also drops avahi, and with it
# raspberrypi.local, which is a way back in when the USB link misbehaves; that
# stays a decision rather than a default.
#
# This has to run here rather than at flash time: it disables cloud-init, which
# a freshly flashed card still needs for its own first boot.
if [[ $DO_BOOT_SPEEDUP -eq 1 ]]; then
  if [[ -x "$SCRIPT_DIR/speed-up-boot.sh" ]]; then
    log "handing off to speed-up-boot.sh"
    "$SCRIPT_DIR/speed-up-boot.sh"
  else
    warn "speed-up-boot.sh not found next to this script; leaving boot services alone"
  fi
fi

# ---------------------------------------------------------------- systemd unit

UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
ENTRY_POINT=""
for candidate in main.py app.py "src/main.py" "nd_timer/__main__.py"; do
  [[ -f "$APP_DIR/$candidate" ]] && { ENTRY_POINT="$candidate"; break; }
done

log "installing $UNIT_PATH"
cat > "$UNIT_PATH" <<UNIT_EOF
[Unit]
Description=ND Long Exposure Timer
# Not multi-user.target. The app needs SPI (a kernel device), the filesystem
# holding the venv, and the account it runs as - and nothing else. Waiting for
# multi-user meant waiting for networking it never uses: measured at 76s on a
# Pi Zero, to start something that takes 3.4s.
#
# Safe because the runtime measures time with time.monotonic(). NTP corrects the
# clock about 80s into boot, jumping it by hours; a wall-clock runtime started
# before that could see a running exposure's elapsed time leap mid-shot.
After=local-fs.target

[Service]
Type=simple
User=${TARGET_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${VENV_DIR}/bin/python ${APP_DIR}/${ENTRY_POINT:-main.py}
Restart=on-failure
RestartSec=5
# The e-paper display needs a clean shutdown or it keeps the last frame burnt in.
KillSignal=SIGINT
TimeoutStopSec=20

[Install]
# basic.target, not multi-user.target: it is reached far earlier and is all this
# needs. The splash is ordered the same way.
WantedBy=basic.target
UNIT_EOF

systemctl daemon-reload

if [[ -n "$ENTRY_POINT" ]]; then
  systemctl enable "$SERVICE_NAME"
  log "enabled ${SERVICE_NAME}.service (entry point: $ENTRY_POINT)"
else
  warn "no entry point found in $APP_DIR; unit installed but left disabled"
  warn "once you have a main.py: sudo systemctl enable --now $SERVICE_NAME"
fi

# ---------------------------------------------------------------- verify

log "verifying"

[[ -e /dev/spidev0.0 ]] \
  && log "SPI: /dev/spidev0.0 present" \
  || warn "SPI: /dev/spidev0.0 missing - it appears after a reboot"

[[ -e /dev/i2c-1 ]] \
  && log "I2C: /dev/i2c-1 present (the UPS HAT's gauge lives here)" \
  || warn "I2C: /dev/i2c-1 missing - it appears after a reboot"

# On a wifi-less Zero the USB gadget link is the only way in, so say plainly
# whether it survived. flash-sd.sh owns these lines; this only reports on them.
CMDLINE="$(dirname "$CONFIG_TXT")/cmdline.txt"
if grep -q '^dtoverlay=dwc2' "$CONFIG_TXT" && grep -q 'modules-load=dwc2,g_ether' "$CMDLINE" 2>/dev/null; then
  log "USB gadget: configured - ssh over the USB port still works after reboot"
else
  warn "USB gadget: NOT configured. On a Pi Zero without wifi this is your only"
  warn "remote access. To enable it, add to $CONFIG_TXT:"
  warn "    dtoverlay=dwc2"
  warn "and append to the single line in $CMDLINE, after rootwait:"
  warn "    modules-load=dwc2,g_ether"
fi

as_user "$VENV_DIR/bin/python" - <<'PY_EOF' || warn "some Python imports failed; check the output above"
import importlib

for module, why in [
    ("PIL", "drawing frames for the e-paper display"),
    ("gpiozero", "buttons"),
    ("spidev", "SPI transport"),
    ("waveshare_epd", "e-paper driver"),
]:
    try:
        importlib.import_module(module)
        print(f"  ok      {module:<16} ({why})")
    except Exception as exc:
        print(f"  MISSING {module:<16} ({why}): {exc}")
PY_EOF

cat <<EOF

========================================================================
  Setup complete - but the device is not running yet. Three steps left.
========================================================================

1. REBOOT. SPI, I2C and the new group memberships only take effect now,
   and nothing below works before it:

       sudo systemctl reboot

2. From your MAC, once it is back up, install the code and start it:

       ./scripts/deploy-to-pi.sh
       ssh -t ${PI_USER:-pi}@10.55.0.1 'sudo systemctl enable --now ${SERVICE_NAME}'

   deploy-to-pi.sh is the one to rerun after every later change. The
   service only has to be enabled by hand this once.

3. Check it came up:

       ssh ${PI_USER:-pi}@10.55.0.1 'systemctl status ${SERVICE_NAME}'
       ssh ${PI_USER:-pi}@10.55.0.1 'journalctl -u ${SERVICE_NAME} -f'

------------------------------------------------------------------------
  If something is wrong
------------------------------------------------------------------------

  display:   ${VENV_DIR}/bin/python scripts/panel-orientation.py
             Solid frames prove the wiring; the letter F proves the
             orientation. Run it with the service stopped.
  camera:    gphoto2 --auto-detect
  buttons:   pinout          # check your wiring against the BCM numbering
  SPI/I2C:   ls /dev/spidev0.0 /dev/i2c-1    # both appear only after the reboot

------------------------------------------------------------------------
  Two things that will bite you
------------------------------------------------------------------------

Gadget mode and the camera both want the one micro-USB data port, so you
cannot have ssh and gphoto2 at the same time. Use scripts/usb-mode.sh to
switch, and note that host mode cuts the only way in - it arms an automatic
revert for exactly that reason.

A LATCHING power switch cuts power with no warning to the OS, which can
corrupt the card mid-write and leaves the e-paper holding a half-drawn
frame. Either run "sudo systemctl halt" and wait for the activity LED to stop, or make
the root filesystem read-only so a hard cut is harmless:

    sudo raspi-config nonint enable_overlayfs   # then reboot

(Wire a separate MOMENTARY button and rerun with --shutdown-pin 3 for a
clean software shutdown instead.)

To undo the config.txt changes: restore ${CONFIG_TXT}.nd-timer.bak
EOF
