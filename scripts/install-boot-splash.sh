#!/usr/bin/env bash
#
# install-boot-splash.sh - show the splash as soon as the panel can be driven.
#
# A Pi Zero takes most of a minute to reach the application. A blank panel for
# that long reads as a device that has not switched on, so this pushes a frame
# packed at build time as early in boot as SPI allows - importing the panel
# driver and nothing else.
#
# Run on the Pi:  sudo ./install-boot-splash.sh [--remove] [--user NAME]
#
# setup-pi.sh calls this for you; it is here separately for a card that was
# provisioned before the splash existed, and for --remove.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
UNIT="/etc/systemd/system/nd-timer-splash.service"
# Whoever will run it. Defaults to the invoking account, but setup-pi.sh has a
# --user of its own and the two must not be allowed to disagree.
SERVICE_USER="${SUDO_USER:-${USER:-pi}}"
REMOVE=0

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Everything below this line assumes the Pi. Run on the Mac, these commands
# either do not exist or aim at the wrong machine - a reboot meant for the timer
# restarts the laptop - so refuse outright instead of half-running.
[[ "$(uname -s)" == "Linux" ]] || die "run this on the Pi, not here (this is $(uname -s))"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remove)  REMOVE=1 ;;
    --user)    SERVICE_USER="${2:?--user needs a name}"; shift ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)         printf 'unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
  shift
done

[[ $EUID -eq 0 ]] || die "run with sudo"

if [[ $REMOVE -eq 1 ]]; then
  systemctl disable --now nd-timer-splash.service >/dev/null 2>&1 || true
  rm -f "$UNIT"
  systemctl daemon-reload
  log "removed"
  exit 0
fi

PYTHON="$APP_DIR/.venv/bin/python"
[[ -x "$PYTHON" ]] || die "no venv at $PYTHON - run scripts/setup-pi.sh first"
[[ -f "$APP_DIR/assets/splash.bin" ]] \
  || die "no packed splash - run scripts/render-screens.py and copy it over"

log "installing $UNIT"
cat > "$UNIT" <<UNIT_EOF
[Unit]
Description=Show the ND timer splash on the e-paper panel
# As early as the panel can be driven: SPI is a kernel device, so the only real
# dependency is that the filesystem holding the buffer is mounted.
#
# DefaultDependencies=no is what makes Before=basic.target legal. Without it
# systemd adds an implicit After=basic.target to every service, which together
# with our Before= is an ordering cycle - and systemd breaks a cycle by deleting
# a job, ours. The unit then sits there enabled and loaded, never runs, and logs
# nothing about it; the only trace is one line in the journal at boot:
#
#   Found ordering cycle on nd-timer-splash.service/start
#   Job nd-timer-splash.service/start deleted to break ordering cycle
#
# Conflicts/Before=shutdown.target is the other half: a unit that opts out of
# default dependencies has to say for itself that it should not outlive a
# shutdown.
#
# Deliberately NOT Before=basic.target. It is a oneshot, so ordering the whole
# basic.target behind it makes every other service wait for a panel refresh -
# measured at 11.6s, which is a cosmetic frame delaying the application it exists
# to paper over. Without it the splash still starts as soon as local-fs is up and
# draws while the rest of the boot carries on beside it.
DefaultDependencies=no
Conflicts=shutdown.target
After=local-fs.target
Before=shutdown.target
ConditionPathExists=/dev/spidev0.0
ConditionPathExists=${APP_DIR}/assets/splash.bin

[Service]
Type=oneshot
RemainAfterExit=yes
User=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${PYTHON} -m nd_timer.boot_splash
# The panel keeps its image with no power, so a failure here costs the splash and
# nothing else. It must never hold up the boot it exists to paper over.
TimeoutStartSec=20
StandardOutput=journal

[Install]
WantedBy=basic.target
UNIT_EOF

systemctl daemon-reload
systemctl enable nd-timer-splash.service 2>&1 | sed 's/^/    /'
systemctl is-enabled nd-timer-splash.service >/dev/null 2>&1 \
  || die "could not enable the unit"

log "enabled. Test it now without rebooting:"
echo "    sudo systemctl start nd-timer-splash && journalctl -u nd-timer-splash -n 20"
warn "if the panel is not wired yet this will fail harmlessly - the unit is oneshot"
warn "and the boot continues regardless."
