#!/usr/bin/env bash
#
# deploy-to-pi.sh - copy this working tree to the Pi and restart the service.
#
# RUNS ON YOUR MAC. It copies code; it does not provision anything - that is
# setup-pi.sh, which runs once on the Pi and installs the venv, the drivers and
# the systemd unit.
#
# It needs key-based ssh, because it is not asking anyone for a password:
#     ssh-copy-id pi@10.55.0.1
#
# The .venv on the Pi is built for armv6 and is not ours to overwrite, so it is
# excluded both from the copy and from the deletion that follows it.
#
# Usage: ./deploy-to-pi.sh [--host pi@10.55.0.1] [--app-dir PATH] [--no-restart]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

HOST="pi@10.55.0.1"
APP_DIR=""
SERVICE_NAME="nd-timer"
RESTART=1

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }
usage() { sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)       HOST="${2:?--host needs user@address}"; shift ;;
    --app-dir)    APP_DIR="${2:?--app-dir needs a path}"; shift ;;
    --no-restart) RESTART=0 ;;
    -h|--help)    usage ;;
    *)            die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

# ------------------------------------------------------------------ the link

# BatchMode so a missing key fails here with a sentence about it, rather than
# hanging on a password prompt inside rsync.
ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" true 2>/dev/null \
  || die "cannot ssh to $HOST without a password.
    Set a key up once:  ssh-copy-id $HOST
    (the Pi answering at all means the link is fine; this is only about the key)"

# systemd knows where the app was installed, which beats guessing at it - but on
# a card that has never had setup-pi.sh run on it there is no unit to ask yet,
# and that is exactly when the first deploy happens. So: ask, and if the answer
# is empty, put it next to the home directory under this repo's own name.
if [[ -z "$APP_DIR" ]]; then
  APP_DIR="$(ssh "$HOST" "systemctl show ${SERVICE_NAME} -p WorkingDirectory --value" 2>/dev/null || true)"
fi
if [[ -z "$APP_DIR" || "$APP_DIR" == "/" ]]; then
  APP_DIR="$(ssh "$HOST" 'echo $HOME')/$(basename "$REPO_DIR")"
  warn "no ${SERVICE_NAME}.service yet - treating this as a first deploy"
  warn "installing to $APP_DIR (override with --app-dir)"
  ssh "$HOST" "mkdir -p '$APP_DIR'" || die "could not create $APP_DIR on $HOST"
fi

log "host:    $HOST"
log "app dir: $APP_DIR"

# ------------------------------------------------------------------ the copy

if [[ -n "$(git -C "$REPO_DIR" status --porcelain 2>/dev/null)" ]]; then
  warn "the working tree has uncommitted changes - they are going to the Pi too"
fi

# --delete keeps the Pi from accumulating files this tree no longer has. rsync
# will not delete anything matched by --exclude, which is what keeps the venv,
# the git history and the caches on the Pi out of its way.
log "copying"
# macOS ships openrsync, not GNU rsync: no --info=, and the patterns want the
# --exclude=pattern form rather than a separate argument.
rsync -a --delete --stats \
  --exclude=.git \
  --exclude=.venv \
  --exclude=__pycache__ \
  --exclude=.pytest_cache \
  --exclude=.idea \
  --exclude='*.pyc' \
  "$REPO_DIR/" "$HOST:$APP_DIR/"

[[ $RESTART -eq 1 ]] || { log "not restarting (--no-restart)"; exit 0; }

# ------------------------------------------------------------------ the service

# setup-pi.sh installs the unit but leaves it disabled when there is no entry
# point yet, which was true until main.py existed. Enabling needs root, and
# nothing here is going to prompt for a password over ssh - so it is attempted
# without one and handed over politely if that is not allowed.
ENABLED="$(ssh "$HOST" "systemctl is-enabled ${SERVICE_NAME} 2>/dev/null || true")"
if [[ "$ENABLED" != "enabled" ]]; then
  warn "${SERVICE_NAME}.service is '${ENABLED:-not installed}' - it has never been started"
  echo "    ssh $HOST 'sudo systemctl enable --now ${SERVICE_NAME}'"
  exit 0
fi

log "restarting ${SERVICE_NAME}"
if ssh "$HOST" "sudo -n systemctl restart ${SERVICE_NAME}" 2>/dev/null; then
  sleep 2
  ssh "$HOST" "systemctl is-active ${SERVICE_NAME}; journalctl -u ${SERVICE_NAME} -n 12 --no-pager"
else
  warn "passwordless sudo is not set up, so the restart is yours:"
  echo "    ssh $HOST 'sudo systemctl restart ${SERVICE_NAME} && journalctl -u ${SERVICE_NAME} -n 20 --no-pager'"
fi
