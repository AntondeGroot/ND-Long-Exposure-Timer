#!/usr/bin/env bash
#
# enable-wifi.sh - make an already-flashed card join a Wi-Fi network and accept
# an ssh key, for when the USB gadget link cannot be used.
#
# RUNS ON YOUR MAC, not on the Pi. It does NOT erase anything. A Zero 2 W only
# has 2.4 GHz Wi-Fi, so the network has to offer that band.
#
# The password is read from a prompt, so it stays out of your shell history and
# the process list. It sits in plain text on the card's boot partition until the
# Pi's first boot deletes it, so do not leave a prepared card lying around.
#
# Usage: ./enable-wifi.sh [--country CC] [--key PUBLIC_KEY] [--boot DIR]
#
#   --country  two-letter Wi-Fi regulatory country (default: NL)
#   --key      public key to authorize (default: ~/.ssh/pi_deploy_key.pub)
#   --boot     boot partition (default: /Volumes/bootfs or /Volumes/boot)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FIRSTRUN="wifi-firstrun.sh"
CREDENTIALS="wifi-credentials"
SSH_KEY="wifi-authorized-key.pub"
MIN_PASSPHRASE_LENGTH=8
MAX_PASSPHRASE_LENGTH=64

COUNTRY="NL"
KEY_SOURCE="$HOME/.ssh/pi_deploy_key.pub"
BOOT=""

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

parse_arguments() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --country) COUNTRY="${2:?--country needs a code}"; shift ;;
      --key)     KEY_SOURCE="${2:?--key needs a path}"; shift ;;
      --boot)    BOOT="${2:?--boot needs a path}"; shift ;;
      -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
      *)         die "unknown option: $1 (try --help)" ;;
    esac
    shift
  done
  [[ "$COUNTRY" =~ ^[A-Z]{2}$ ]] || die "--country must be two capital letters, like NL"
  [[ -f "$KEY_SOURCE" ]] || die "no public key at $KEY_SOURCE (use --key)"
  [[ -f "$SCRIPT_DIR/$FIRSTRUN" ]] || die "missing $SCRIPT_DIR/$FIRSTRUN"
}

find_boot_partition() {
  local candidate marker
  if [[ -z "$BOOT" ]]; then
    for candidate in /Volumes/bootfs /Volumes/boot; do
      [[ -d "$candidate" ]] && { BOOT="$candidate"; break; }
    done
  fi
  [[ -n "$BOOT" ]] || die "no Pi boot partition mounted - put the card in the reader first"
  for marker in cmdline.txt config.txt; do
    [[ -f "$BOOT/$marker" ]] || die "$BOOT has no $marker - that does not look like a Pi boot partition"
  done
}

# systemd.run= holds one script, so a second hook would silently replace the
# first. An unfinished one means the card has not booted since it was added.
refuse_a_foreign_boot_hook() {
  ! grep -q 'systemd\.run=' "$BOOT/cmdline.txt" && return
  grep -q "systemd\.run=/boot/firmware/$FIRSTRUN" "$BOOT/cmdline.txt" && return
  die "cmdline.txt already runs another first-boot script. Boot the card once to let it finish, then rerun this."
}

passphrase_is_valid() {
  local passphrase="$1"
  [[ ${#passphrase} -ge $MIN_PASSPHRASE_LENGTH && ${#passphrase} -le $MAX_PASSPHRASE_LENGTH ]] || return 1
  [[ "$passphrase" != [[:space:]]* && "$passphrase" != *[[:space:]] ]]
}

write_credentials() {
  local ssid passphrase repeated
  read -r -p "Wi-Fi network name (2.4 GHz): " ssid
  [[ -n "$ssid" ]] || die "empty network name"
  read -r -s -p "Wi-Fi password: " passphrase; echo
  read -r -s -p "Repeat: " repeated; echo
  [[ "$passphrase" == "$repeated" ]] || die "passwords do not match"
  passphrase_is_valid "$passphrase" \
    || die "a WPA password is $MIN_PASSPHRASE_LENGTH-$MAX_PASSPHRASE_LENGTH characters, with no space at either end"
  printf '%s\n%s\n' "$ssid" "$passphrase" > "$BOOT/$CREDENTIALS"
}

add_to_cmdline() {
  local addition="$1"
  printf '%s %s\n' "$(tr -d '\n' < "$BOOT/cmdline.txt")" "$addition" > "$BOOT/cmdline.txt.new"
  mv "$BOOT/cmdline.txt.new" "$BOOT/cmdline.txt"
}

# systemd.run hijacks the next boot to run our script, then reboots into the real
# system. The country stays, because Wi-Fi needs it on every boot.
install_boot_hook() {
  cp -X "$BOOT/cmdline.txt" "$BOOT/cmdline.txt.bak"
  grep -q 'cfg80211\.ieee80211_regdom=' "$BOOT/cmdline.txt" \
    || add_to_cmdline "cfg80211.ieee80211_regdom=$COUNTRY"
  grep -q 'systemd\.run=' "$BOOT/cmdline.txt" \
    || add_to_cmdline "systemd.run=/boot/firmware/$FIRSTRUN systemd.run_success_action=reboot systemd.unit=kernel-command-line.target"
  [[ "$(wc -l < "$BOOT/cmdline.txt")" -le 1 ]] \
    || die "cmdline.txt must be a single line - restore $BOOT/cmdline.txt.bak before booting"
}

main() {
  parse_arguments "$@"
  find_boot_partition
  refuse_a_foreign_boot_hook

  log "card: $BOOT   country: $COUNTRY   key: $KEY_SOURCE"
  write_credentials
  cp -X "$KEY_SOURCE" "$BOOT/$SSH_KEY"
  cp -X "$SCRIPT_DIR/$FIRSTRUN" "$BOOT/$FIRSTRUN"
  chmod +x "$BOOT/$FIRSTRUN" 2>/dev/null || true
  touch "$BOOT/.metadata_never_index" 2>/dev/null || true
  install_boot_hook
  sync

  log "card ready. Put it in the Pi and power it up; it reboots itself once."
  log "If it never joins, read $BOOT/wifi-setup.log with the card back in this Mac."
}

main "$@"
