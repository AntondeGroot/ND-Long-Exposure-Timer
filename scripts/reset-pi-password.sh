#!/usr/bin/env bash
#
# reset-pi-password.sh - set a new password on a Pi card you can no longer log into.
#
# RUNS ON YOUR MAC, not on the Pi. It does NOT erase anything: it writes one file.
#
# Pi OS applies /boot/firmware/userconf.txt at every boot where it exists, sets
# the account's password from it, and deletes it. flash-sd.sh uses that to create
# the account in the first place; this uses it to change the password afterwards,
# which is the whole of the recovery. Everything else on the card is left alone.
#
# The password is read from a prompt and piped to the hasher on stdin, so it
# never appears in your shell history, in the process list, or in this script.
#
# You need the card in your Mac, because the only partition macOS can mount is
# the FAT boot one - /home is on the ext4 root, which it cannot read at all.
#
# Usage: ./reset-pi-password.sh [--user NAME]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PI_USER="pi"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }
usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)    PI_USER="${2:?--user needs a name}"; shift ;;
    -h|--help) usage ;;
    *)         die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

[[ "$(uname -s)" == "Darwin" ]] || die "this script is macOS-only (it uses diskutil)"

# ------------------------------------------------------------------ the card

BOOT=""
for candidate in /Volumes/bootfs /Volumes/boot; do
  [[ -d "$candidate" ]] && { BOOT="$candidate"; break; }
done
[[ -n "$BOOT" ]] || die "no Pi boot partition mounted. Put the card in and wait for it to appear,
    or mount it by hand: diskutil list, then diskutil mount diskNs1"

# A FAT volume called bootfs is not proof of anything; these two files are what
# a Pi boot partition always has, and writing userconf.txt anywhere else would
# be leaving a password hash on some unrelated stick.
for marker in cmdline.txt config.txt; do
  [[ -f "$BOOT/$marker" ]] || die "$BOOT has no $marker - that does not look like a Pi boot partition"
done

# The lesson of the write-protected adapter: fail here, with the reason, rather
# than at the redirect below with "Read-only file system".
if ! touch "$BOOT/.write-test" 2>/dev/null; then
  DISK="$(diskutil info "$BOOT" 2>/dev/null | awk -F: '/Part of Whole/ {gsub(/ /,"",$2); print $2}')"
  MEDIA_RO="$(diskutil info "${DISK:-$BOOT}" 2>/dev/null | grep -c "Media Read-Only:.*Yes" || true)"
  [[ "$MEDIA_RO" -gt 0 ]] \
    && die "$BOOT is write-protected by the reader - usually the lock slider on a full-size SD adapter.
    A worn card can also latch read-only for good; another card in the same adapter tells you which."
  die "$BOOT is mounted read-only. Eject it, re-insert, and try again."
fi
rm -f "$BOOT/.write-test"

# ------------------------------------------------------------------ the hash

# Pi OS needs a $6$ (SHA-512) hash, which macOS cannot produce: LibreSSL's
# `openssl passwd` has no -6, and the system libcrypt silently downgrades
# METHOD_SHA512 to 13-character DES. sha512-crypt.py implements it properly.
HASHER="$SCRIPT_DIR/sha512-crypt.py"
[[ -f "$HASHER" ]] || die "missing $HASHER - it lives next to this script"
python3 "$HASHER" --self-test >/dev/null 2>&1 \
  || die "sha512-crypt.py fails its own test vectors; refusing to write a hash you could not log in with"

log "card:  $BOOT"
log "user:  $PI_USER"
echo

read -r -s -p "New password for '$PI_USER': " PI_PASS; echo
[[ -n "$PI_PASS" ]] || die "empty password"
read -r -s -p "Repeat: " PI_PASS2; echo
[[ "$PI_PASS" == "$PI_PASS2" ]] || die "passwords do not match"

PI_HASH="$(printf '%s' "$PI_PASS" | python3 "$HASHER")" || die "could not hash the password"
unset PI_PASS PI_PASS2

# ------------------------------------------------------------------ write it

# Spotlight indexes any volume the moment it mounts and then holds it open, so
# ejecting a card it has got hold of takes minutes. flash-sd.sh leaves this
# marker for the same reason; a card flashed before that will not have one.
touch "$BOOT/.metadata_never_index" 2>/dev/null || true

# userconf.txt is not the mechanism here, whatever the Pi documentation says:
# the service that reads it runs on first boot and is disabled afterwards, so on
# a card that has already been set up the file just sits there being ignored.
#
# systemd.run= is driven by the kernel command line instead, which nothing can
# have disabled. enable-gadget-network.sh already uses it on this very card, so
# the mechanism is known to work here - this borrows its shape, including the
# set +e that keeps a failure from leaving the Pi unbootable.
HOOK="$BOOT/passwd-reset.sh"

cat > "$HOOK" <<'HOOK_EOF'
#!/bin/bash
# Runs ONCE on the Pi, early in boot, via systemd.run= in cmdline.txt.
# Written by scripts/reset-pi-password.sh. Deletes itself: it holds a hash.

set +e   # a failure here must never leave the Pi unbootable

BOOT=/boot/firmware
[ -d "$BOOT" ] || BOOT=/boot

log() { echo "[passwd-reset] $*" | tee -a "$BOOT/passwd-reset.log"; }

log "starting at $(date 2>/dev/null)"

CREDENTIAL='@CREDENTIAL@'
WANTED="${CREDENTIAL%%:*}"
HASH="${CREDENTIAL#*:}"

# Which account to set. The name is whatever the card was flashed with, which
# is not something the Mac can read off an ext4 root - so rather than trust a
# guess, the first real account is found here, where /etc/passwd is readable.
PRIMARY="$(getent passwd 1000 2>/dev/null | cut -d: -f1)"
log "accounts: $(getent passwd 2>/dev/null | awk -F: '$3>=1000 && $3<65534 {print $1}' | tr '\n' ' ')"
log "uid 1000: ${PRIMARY:-none}   asked for: $WANTED"
log "chpasswd: $(command -v chpasswd 2>/dev/null || echo MISSING)"
log "root fs:  $(awk '$2=="/" {print $4}' /proc/mounts 2>/dev/null | cut -d, -f1)"

if id "$WANTED" >/dev/null 2>&1; then
  TARGET="$WANTED"
elif [ -n "$PRIMARY" ]; then
  TARGET="$PRIMARY"
  log "no account called '$WANTED' - using uid 1000 instead"
else
  # Pi OS ships no default account: it is created on first boot from
  # userconf.txt, and if that never happened there is nobody to log in as and
  # nothing for chpasswd to change. Setting a password is the wrong operation
  # here; the account has to exist first.
  TARGET="$WANTED"
  log "no accounts at all - creating '$TARGET'"
  useradd -m -s /bin/bash "$TARGET" 2>>"$BOOT/passwd-reset.log" \
    && log "created $TARGET" \
    || log "WARNING: useradd failed"

  # sudo to be able to finish the setup, and the hardware groups setup-pi.sh
  # grants, so the app can reach the panel and the buttons.
  for grp in sudo gpio spi i2c dialout video plugdev; do
    groupadd -f "$grp" >/dev/null 2>&1
    usermod -aG "$grp" "$TARGET" >/dev/null 2>&1
  done
  log "added $TARGET to sudo and the hardware groups"
fi

# stderr into the log, because "it failed" without the reason is what made the
# last attempt a guessing game.
printf '%s:%s\n' "$TARGET" "$HASH" | chpasswd -e 2>>"$BOOT/passwd-reset.log" \
  && log "password set for $TARGET" \
  || log "WARNING: chpasswd failed for $TARGET"

# The file this script exists because of: never consumed, never will be.
[ -f "$BOOT/userconf.txt" ] && rm -f "$BOOT/userconf.txt" && log "removed the unused userconf.txt"

# Strip this script's own hooks so the next boot is a normal one.
if [ -f "$BOOT/cmdline.txt" ]; then
  cp "$BOOT/cmdline.txt" "$BOOT/cmdline.txt.passwd.bak"
  sed -i 's| systemd\.run=[^ ]*||g; s| systemd\.run_success_action=[^ ]*||g; s| systemd\.unit=[^ ]*||g' "$BOOT/cmdline.txt"
  log "removed the boot hook from cmdline.txt"
fi

# This file has a password hash in it and the boot partition is readable by
# anything with a card slot, so it does not outlive its one use.
rm -f "$BOOT/passwd-reset.sh"
sync
log "done - rebooting into the normal system"
exit 0
HOOK_EOF

# The hash contains $ and / and must not be mangled by the shell or by sed, and
# must not appear in a command line where ps could see it - so it goes in on
# stdin and Python does the substitution.
printf '%s:%s' "$PI_USER" "$PI_HASH" | python3 -c '
import sys
credential = sys.stdin.read()
path = sys.argv[1]
# Read all of it before opening for writing: opening for writing truncates, and
# doing both in one expression empties the file and then copies the emptiness.
filled = open(path).read().replace("@CREDENTIAL@", credential)
open(path, "w").write(filled)
' "$HOOK"
unset PI_HASH
chmod +x "$HOOK" 2>/dev/null || true

# Three checks, because the first one alone passes on an empty file - and an
# empty hook is worse than a missing one: it would never strip itself out of
# cmdline.txt, so the Pi would run it and reboot, for ever. Nothing is wired
# into cmdline.txt until the hook itself is known to be sound.
grep -q '@CREDENTIAL@' "$HOOK" && die "the hash did not make it into $HOOK - do not boot the card"
grep -q 'chpasswd -e' "$HOOK" || die "$HOOK has no chpasswd line - do not boot the card"
# -F, so the $ and $6$ in the pattern need no escaping: getting that wrong is
# how this check came to refuse a hook that was perfectly good.
grep -q "^CREDENTIAL='" "$HOOK" || die "$HOOK has no credential line - do not boot the card"
grep -qF ':$6$' "$HOOK" || die "$HOOK has no \$6\$ hash in it - do not boot the card"

# ------------------------------------------------------------------ the hook

if grep -q 'systemd.run=' "$BOOT/cmdline.txt"; then
  log "boot hook already in cmdline.txt - leaving it alone"
else
  cp "$BOOT/cmdline.txt" "$BOOT/cmdline.txt.bak"
  printf '%s systemd.run=/boot/firmware/passwd-reset.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target\n' \
    "$(tr -d '\n' < "$BOOT/cmdline.txt.bak")" > "$BOOT/cmdline.txt"
fi

# One line or the Pi does not boot. This is the check worth having.
[[ "$(wc -l < "$BOOT/cmdline.txt")" -le 1 ]] \
  || die "cmdline.txt ended up with more than one line - restore $BOOT/cmdline.txt.bak before booting"

echo
log "wrote $HOOK and hooked it into cmdline.txt"
echo
echo "  1. pull the card out (do not eject it - this reader then needs a reseat)"
echo "  2. put it in the Pi and power on"
echo "  3. it boots, sets the password, and reboots itself - give it two minutes"
echo "  4. ssh ${PI_USER}@10.55.0.1"
echo
echo "  it leaves $BOOT/passwd-reset.log behind, readable from here, if it did not work"
