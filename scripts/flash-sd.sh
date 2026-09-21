#!/usr/bin/env bash
#
# flash-sd.sh - write Raspberry Pi OS Lite to an SD card for a Pi Zero (non-W),
# configured for headless access over USB gadget mode.
#
# RUNS ON YOUR MAC, not on the Pi. It ERASES the target disk.
#
# The plain Pi Zero has no wifi, so the card comes out pre-configured to appear
# as a USB ethernet adapter: plug the Pi's USB port (not PWR) into the Mac and
# ssh to raspberrypi.local. That link uses the same port the camera needs, so it
# is a bring-up convenience, not the final wiring.
#
# What it writes to the boot partition:
#   ssh           - enables sshd on first boot
#   userconf.txt  - your account + hashed password (Pi OS has no default user)
#   config.txt    - dtoverlay=dwc2
#   cmdline.txt   - modules-load=dwc2,g_ether after rootwait
#
# Usage: ./flash-sd.sh --disk /dev/diskN [--user NAME] [--image PATH] [--keep-image]
#        ./flash-sd.sh --list
#
# It refuses a disk too large to be a card unless --allow-large says otherwise.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DISK=""
PI_USER="pi"
ALLOW_LARGE=0

# Bigger than any card anyone puts in a Pi Zero, and smaller than the drives
# that get plugged into the same Mac. Cards do come larger - 512GB microSD is a
# real product - so this is a stop rather than a ban, and --allow-large is how
# you say you meant it. Decimal GB, because that is what diskutil reports.
MAX_CARD_BYTES=$((256 * 1000 * 1000 * 1000))
IMAGE=""
KEEP_IMAGE=0
CACHE_DIR="${TMPDIR:-/tmp}/pi-images"
IMAGE_URL="https://downloads.raspberrypi.com/raspios_lite_armhf_latest"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

usage() { sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

# Spotlight starts indexing a volume the instant it mounts and then holds it
# open, so diskutil reports "Unmount ... dissented by PID nnn (mds_stores)".
# Waiting it out beats failing; forcing is the last resort. Safe once the data
# is written and synced - it only breaks the indexer's handle.
detach_disk() {
  local action="$1" disk="$2" attempt
  for attempt in 1 2 3 4 5; do
    diskutil "$action" "$disk" >/dev/null 2>&1 && return 0
    [[ $attempt -eq 1 ]] && log "$disk is busy (Spotlight is probably indexing it); retrying"
    sleep 2
  done
  warn "$action still dissented after 5 tries; forcing"
  diskutil unmountDisk force "$disk" >/dev/null 2>&1 || return 1
  if [[ "$action" == "eject" ]]; then
    diskutil eject "$disk" >/dev/null 2>&1 || return 1
  fi
  return 0
}

list_disks() {
  log "removable disks (includes the built-in SD slot, which reports as internal):"
  diskutil list physical | grep -v "^$" || true
  echo
  echo "Pick the one whose size matches your SD card. Getting this wrong erases the wrong disk."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --disk)       DISK="${2:?--disk needs /dev/diskN}"; shift ;;
    --user)       PI_USER="${2:?--user needs a name}"; shift ;;
    --image)      IMAGE="${2:?--image needs a path}"; shift ;;
    --keep-image) KEEP_IMAGE=1 ;;
    --allow-large) ALLOW_LARGE=1 ;;
    --list)       list_disks; exit 0 ;;
    -h|--help)    usage ;;
    *)            die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

[[ "$(uname -s)" == "Darwin" ]] || die "this script is macOS-only (it uses diskutil)"
[[ -n "$DISK" ]] || { list_disks; die "no target given: rerun with --disk /dev/diskN"; }

# ---------------------------------------------------------------- target checks

[[ "$DISK" =~ ^/dev/disk[0-9]+$ ]] || die "expected a whole disk like /dev/disk4, got: $DISK"

INFO="$(diskutil info "$DISK" 2>/dev/null)" || die "no such disk: $DISK"

# Removability is the safety property, not location: a Mac's built-in SDXC slot
# reports "Device Location: Internal" for a perfectly removable card, so keying
# on location alone refuses the most obvious way to flash one.
grep -qE "Removable Media:.*(Removable|Yes)" <<<"$INFO" \
  || die "$DISK is not removable media. Refusing. Use --list to find the SD card."

# A write-protected card passes every other check here - it is removable, it is
# not the boot disk, it is the right size - and then dd fails minutes later with
# a permission error that reads like a sudo problem. The reader has already told
# us, in the same blob we are parsing; the usual cause is the lock slider on a
# full-size adapter, which a microSD card cannot have been locked by itself.
grep -qE "Media Read-Only:.*Yes" <<<"$INFO" \
  && die "$DISK reports itself write-protected - the reader, not the filesystem, and not the mount.
    Usually the lock slider on a full-size SD adapter. A worn card can also latch read-only for good."

# Whole-system disks are never removable, but be explicit: never touch the boot disk.
BOOT_DISK="$(diskutil info / 2>/dev/null | awk -F: '/Part of Whole/ {gsub(/ /,"",$2); print $2}')"
[[ "$DISK" != "/dev/${BOOT_DISK}" ]] || die "$DISK is this Mac's boot disk. Refusing."

DISK_NAME="$(awk -F: '/Device \/ Media Name/ {gsub(/^ +/,"",$2); print $2}' <<<"$INFO" | head -1)"
DISK_SIZE="$(awk -F: '/Disk Size/ {gsub(/^ +/,"",$2); print $2}' <<<"$INFO" | head -1)"
DISK_PROTOCOL="$(awk -F: '/^ *Protocol:/ {gsub(/^ +/,"",$2); print $2}' <<<"$INFO" | head -1)"
DISK_BYTES="$(grep -oE '\([0-9]+ Bytes\)' <<<"$INFO" | head -1 | tr -cd '0-9')"

# Removable is not the same as unimportant: an external SSD is removable, is not
# the boot disk, and is the size of everything you own. Size is the only thing
# that separates it from a card here, because a USB card reader and a USB drive
# are the same protocol - so the Mac's own slot, which says "Secure Digital"
# outright, is taken at its word and everything else is judged by how big it is.
#
# The typed ERASE below is not enough on its own. By the time you are typing it
# you have already decided, and "500.3 GB" three lines up is exactly the sort of
# thing a decided person reads past.
if [[ "$DISK_PROTOCOL" != "Secure Digital" && $ALLOW_LARGE -eq 0 ]] \
  && [[ -n "$DISK_BYTES" && "$DISK_BYTES" -gt "$MAX_CARD_BYTES" ]]; then
  die "$DISK is ${DISK_SIZE:-an unknown size} - too big to be a Pi card, and this erases it with dd.
    name:     ${DISK_NAME:-unknown}
    protocol: ${DISK_PROTOCOL:-unknown}
  If that really is your card, rerun with --allow-large."
fi

echo
warn "About to ERASE: $DISK"
warn "  name: ${DISK_NAME:-unknown}"
warn "  size: ${DISK_SIZE:-unknown}"
echo
read -r -p "Type ERASE to confirm: " reply
[[ "$reply" == "ERASE" ]] || die "aborted"

# ---------------------------------------------------------------- credentials

# Pi OS Bookworm ships no default account; without userconf.txt you cannot log in.
read -r -s -p "Password for user '$PI_USER' on the Pi: " PI_PASS; echo
[[ -n "$PI_PASS" ]] || die "empty password"
read -r -s -p "Repeat: " PI_PASS2; echo
[[ "$PI_PASS" == "$PI_PASS2" ]] || die "passwords do not match"

# Pi OS needs a $6$ (SHA-512) hash. macOS cannot produce one: LibreSSL's
# `openssl passwd` has no -6, and the system libcrypt silently downgrades
# METHOD_SHA512 to 13-character DES, so Python's crypt module lies about it.
# sha512-crypt.py implements the algorithm; its vectors are checked against glibc.
HASHER="$SCRIPT_DIR/sha512-crypt.py"
[[ -f "$HASHER" ]] || die "missing $HASHER - it lives next to this script"

python3 "$HASHER" --self-test >/dev/null 2>&1 \
  || die "sha512-crypt.py fails its own test vectors; refusing to write a card you could not log into"

PI_HASH="$(printf '%s' "$PI_PASS" | python3 "$HASHER")" || die "could not hash the password"
[[ "$PI_HASH" == \$6\$*\$* && ${#PI_HASH} -ge 90 ]] \
  || die "hash does not look like SHA-512 crypt: $PI_HASH"

# ---------------------------------------------------------------- get the image

mkdir -p "$CACHE_DIR"

if [[ -z "$IMAGE" ]]; then
  log "resolving the latest Raspberry Pi OS Lite (armhf - the 32-bit build the Zero needs)"
  RESOLVED="$(curl -sIL -o /dev/null -w '%{url_effective}' "$IMAGE_URL")"
  [[ "$RESOLVED" == *.img.xz ]] || die "unexpected image URL: $RESOLVED"

  IMAGE="$CACHE_DIR/$(basename "$RESOLVED")"
  if [[ -f "$IMAGE" ]]; then
    log "using cached $(basename "$IMAGE")"
  else
    log "downloading $(basename "$RESOLVED") (~500MB)"
    curl -fL --retry 3 -o "$IMAGE.part" "$RESOLVED"
    mv "$IMAGE.part" "$IMAGE"
  fi

  log "verifying checksum"
  if EXPECTED="$(curl -fsSL "${RESOLVED}.sha256" 2>/dev/null | awk '{print $1}')" && [[ -n "$EXPECTED" ]]; then
    ACTUAL="$(shasum -a 256 "$IMAGE" | awk '{print $1}')"
    [[ "$EXPECTED" == "$ACTUAL" ]] || die "CHECKSUM MISMATCH - expected $EXPECTED, got $ACTUAL. Delete $IMAGE and retry."
    log "checksum ok"
  else
    warn "could not fetch the published checksum; skipping verification"
  fi
fi

[[ -f "$IMAGE" ]] || die "image not found: $IMAGE"

# ---------------------------------------------------------------- write

# macOS has no xz(1) by default; python3's lzma module is the fallback.
decompress_to_stdout() {
  if [[ "$IMAGE" != *.xz ]]; then cat "$IMAGE"; return; fi
  if command -v xz >/dev/null; then xz -dc "$IMAGE"; return; fi
  python3 - "$IMAGE" <<'PY_EOF'
import lzma, sys, shutil
with lzma.open(sys.argv[1], "rb") as src:
    shutil.copyfileobj(src, sys.stdout.buffer, 1024 * 1024)
PY_EOF
}

# pv does this better, but it is not on a stock macOS - and without something
# here the write is ten silent minutes. Ctrl-T cannot fill the gap: SIGINFO goes
# to sudo, which does not pass it down to the dd underneath, so all it prints is
# the shell's own load average.
progress_meter() {
  TOTAL_BYTES="$1" python3 -c '
import os, sys, time

total = int(os.environ.get("TOTAL_BYTES") or 0)
out = sys.stdout.buffer
done = 0
start = last = time.monotonic()

while True:
    chunk = sys.stdin.buffer.read(1024 * 1024)
    if not chunk:
        break
    out.write(chunk)
    done += len(chunk)

    now = time.monotonic()
    if now - last < 1.0:
        continue
    last = now
    elapsed = now - start
    rate = done / elapsed if elapsed else 0
    if total and rate:
        left = int((total - done) / rate)
        note = f"{100 * done / total:5.1f}%   {done / 1e9:4.2f} of {total / 1e9:4.2f} GB   {rate / 1e6:5.1f} MB/s   ~{left // 60}m{left % 60:02d}s left"
    else:
        note = f"{done / 1e9:4.2f} GB   {rate / 1e6:5.1f} MB/s   {int(elapsed)}s"
    print("\r    " + note + "    ", end="", file=sys.stderr, flush=True)

out.flush()
print(file=sys.stderr)
'
}

log "unmounting $DISK"
detach_disk unmountDisk "$DISK" || die "could not unmount $DISK - close anything using it and retry"

RAW_DISK="${DISK/\/dev\/disk//dev/rdisk}"   # raw device: an order of magnitude faster

# The uncompressed size, so the meter can show a percentage rather than a
# number that means nothing until it stops going up. xz keeps it in the stream
# footer, which is why this costs nothing to read.
TOTAL_BYTES=0
if [[ "$IMAGE" == *.xz ]]; then
  command -v xz >/dev/null \
    && TOTAL_BYTES="$(xz --robot --list "$IMAGE" 2>/dev/null | awk '/^totals/ {print $5}')"
else
  TOTAL_BYTES="$(stat -f%z "$IMAGE" 2>/dev/null || echo 0)"
fi
TOTAL_BYTES="${TOTAL_BYTES:-0}"

log "writing to $RAW_DISK - several minutes; the card's write speed decides how many"
if command -v pv >/dev/null; then
  if [[ "$TOTAL_BYTES" -gt 0 ]]; then
    decompress_to_stdout | pv -s "$TOTAL_BYTES" | sudo dd of="$RAW_DISK" bs=4m
  else
    decompress_to_stdout | pv | sudo dd of="$RAW_DISK" bs=4m
  fi
else
  decompress_to_stdout | progress_meter "$TOTAL_BYTES" | sudo dd of="$RAW_DISK" bs=4m
fi
sync

# ---------------------------------------------------------------- configure boot

log "waiting for the boot partition to mount"
BOOT=""
for _ in $(seq 1 20); do
  diskutil mountDisk "$DISK" >/dev/null 2>&1 || true
  for candidate in /Volumes/bootfs /Volumes/boot; do
    [[ -d "$candidate" ]] && { BOOT="$candidate"; break 2; }
  done
  sleep 1
done
[[ -n "$BOOT" ]] || die "boot partition did not mount; re-insert the card and configure it by hand"

log "configuring $BOOT for headless USB gadget access"

# Tells Spotlight never to index this volume, here or on any future insert.
# Harmless on the Pi - just a hidden empty file in /boot/firmware.
touch "$BOOT/.metadata_never_index"

touch "$BOOT/ssh"
printf '%s:%s\n' "$PI_USER" "$PI_HASH" > "$BOOT/userconf.txt"

# dwc2 puts the USB controller in peripheral mode; g_ether makes it an ethernet
# device. Two traps here:
#   - Stock Bookworm already ships "dtoverlay=dwc2,dr_mode=host" under [cm5], so
#     a loose grep for dtoverlay=dwc2 matches a line that is both host mode and
#     scoped to a different board, and we would skip adding our own.
#   - config.txt is section-scoped, so the line must sit under [all] to reach a
#     Zero, whatever section the file happens to end in.
if ! grep -q '^dtoverlay=dwc2,dr_mode=peripheral' "$BOOT/config.txt"; then
  cat >> "$BOOT/config.txt" <<'CFG_EOF'

# USB gadget mode - lets a headless Pi Zero appear as an ethernet device over
# its USB port. Added by scripts/flash-sd.sh.
[all]
dtoverlay=dwc2,dr_mode=peripheral
CFG_EOF
fi

# cmdline.txt must stay a single line, so the modules go inline after rootwait.
if ! grep -q 'modules-load=dwc2,g_ether' "$BOOT/cmdline.txt"; then
  cp "$BOOT/cmdline.txt" "$BOOT/cmdline.txt.bak"
  sed -i '' 's/rootwait/rootwait modules-load=dwc2,g_ether/' "$BOOT/cmdline.txt"
  grep -q 'modules-load=dwc2,g_ether' "$BOOT/cmdline.txt" \
    || die "could not patch cmdline.txt (no 'rootwait' found); add modules-load=dwc2,g_ether by hand"
  [[ "$(wc -l < "$BOOT/cmdline.txt")" -le 1 ]] || warn "cmdline.txt now has more than one line - that breaks boot"
fi

log "boot partition contents:"
ls -1 "$BOOT" | sed 's/^/    /'

sync

# Unmounted, not ejected. Unmounting flushes everything and makes the card safe
# to pull out, while leaving the device attached so it can be mounted again -
# and the next step, enable-gadget-network.sh, needs exactly that. An eject
# detaches the whole device on a built-in reader, and nothing brings it back
# but taking the card out and putting it in again.
if detach_disk unmountDisk "$DISK"; then
  log "unmounted $DISK - safe to pull out, and still there if you need it mounted"
else
  warn "the card is written and configured, but macOS would not unmount it."
  warn "run this before pulling it out: diskutil unmountDisk force $DISK"
fi

[[ $KEEP_IMAGE -eq 1 ]] || log "image kept at $IMAGE (use --keep-image to silence this)"

cat <<EOF

Card is written. It is NOT ready to boot yet.

  1. With the card still in this Mac, run:
         ./scripts/enable-gadget-network.sh
     Bookworm brings the ethernet gadget up but never gives usb0 an address, so
     without this the Pi boots with no link and the only way back in is the card.

  2. Put the card in the Pi Zero.
  3. Connect the Mac to the Pi's micro-USB port marked USB - NOT the one marked PWR.
     That single cable powers it and carries the network link.
  4. Wait ~90 seconds for the first boot (it resizes the filesystem and reboots).
  5. ssh ${PI_USER}@10.55.0.1

Then, from the Mac:
    ssh-copy-id -i ~/.ssh/pi_deploy_key.pub ${PI_USER}@10.55.0.1   # in a real terminal
    ./scripts/deploy-to-pi.sh                                      # copies this tree over

And on the Pi, once:
    sudo ./scripts/setup-pi.sh
EOF
