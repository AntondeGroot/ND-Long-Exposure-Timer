#!/usr/bin/env bash
#
# install-boot-splash.sh - show the splash as soon as the panel can be driven.
#
# A Pi Zero takes most of a minute to reach the application. A blank panel for
# that long reads as a device that has not switched on, so this pushes a frame
# packed at build time as early in boot as SPI allows - importing the panel
# driver and nothing else.
#
# Run on the Pi:  sudo ./install-boot-splash.sh [--remove]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
UNIT="/etc/systemd/system/nd-timer-splash.service"
SERVICE_USER="${SUDO_USER:-${USER:-pi}}"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run with sudo"

if [[ "${1:-}" == "--remove" ]]; then
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
After=local-fs.target
Before=basic.target
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
