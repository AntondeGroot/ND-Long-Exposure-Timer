#!/usr/bin/env bash
#
# fix-gadget-from-linux.sh - configure the Pi Zero's USB ethernet gadget by
# editing its SD card directly from another Linux box.
#
# Run this on a Linux machine (e.g. the Pi 4) with the Zero's card in a reader.
# Unlike editing from macOS, Linux can mount the ext4 root filesystem, so the
# network configuration goes exactly where it belongs instead of being smuggled
# in through a first-boot script that may never run.
#
# It writes, on the card's root filesystem:
#   /etc/NetworkManager/conf.d/99-usb0-unmanaged.conf   keep NM off usb0
#   /etc/systemd/system/usb0-static.service             static address on usb0
#   .../multi-user.target.wants/usb0-static.service     the enable symlink
# and on the boot partition, restores a clean cmdline: g_ether, no firstrun hook,
# no ttyGS0 console.
#
# Usage: sudo ./fix-gadget-from-linux.sh [--device /dev/sdX] [--dry-run]

set -euo pipefail

PI_ADDR="10.55.0.1/24"
DEVICE=""
DRY_RUN=0
MNT_BOOT="/mnt/pi-boot"
MNT_ROOT="/mnt/pi-root"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --device)  DEVICE="${2:?--device needs /dev/sdX}"; shift ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)         die "unknown option: $1" ;;
  esac
  shift
done

[[ "$(uname -s)" == "Linux" ]] || die "run this on Linux - macOS cannot mount ext4"
[[ $EUID -eq 0 ]] || die "run with sudo"

# ---------------------------------------------------------------- find the card

if [[ -z "$DEVICE" ]]; then
  log "looking for a removable disk with a Raspberry Pi layout"
  while read -r name type rm; do
    [[ "$type" == "disk" && "$rm" == "1" ]] || continue
    dev="/dev/$name"
    # A Pi card is a FAT boot partition followed by an ext4 root partition.
    if lsblk -no FSTYPE "$dev" | tr '\n' ' ' | grep -q 'vfat.*ext4'; then
      DEVICE="$dev"; break
    fi
  done < <(lsblk -dno NAME,TYPE,RM)
fi

[[ -n "$DEVICE" ]] || die "no Pi card found - pass --device /dev/sdX (check lsblk)"

BOOT_PART="${DEVICE}1"
ROOT_PART="${DEVICE}2"
[[ -b "$BOOT_PART" && -b "$ROOT_PART" ]] || die "expected $BOOT_PART and $ROOT_PART to exist"

log "using $DEVICE (boot=$BOOT_PART root=$ROOT_PART)"
lsblk -o NAME,SIZE,FSTYPE,LABEL "$DEVICE" | sed 's/^/    /'

# Refuse to touch the disk this machine is running from.
running_on="$(findmnt -no SOURCE / | sed 's/[0-9]*$//')"
[[ "$DEVICE" != "$running_on" ]] || die "$DEVICE is this machine's own root disk - refusing"

if [[ $DRY_RUN -eq 1 ]]; then
  log "dry run - stopping before any changes"
  exit 0
fi

# ---------------------------------------------------------------- mount

mkdir -p "$MNT_BOOT" "$MNT_ROOT"
cleanup() {
  sync
  umount "$MNT_BOOT" 2>/dev/null || true
  umount "$MNT_ROOT" 2>/dev/null || true
}
trap cleanup EXIT

mount "$BOOT_PART" "$MNT_BOOT" || die "could not mount $BOOT_PART"
mount "$ROOT_PART" "$MNT_ROOT" || die "could not mount $ROOT_PART"
log "mounted both partitions"

[[ -d "$MNT_ROOT/etc/systemd/system" ]] || die "$ROOT_PART does not look like a Pi root filesystem"

# ---------------------------------------------------------------- root fs

log "writing NetworkManager override"
mkdir -p "$MNT_ROOT/etc/NetworkManager/conf.d"
cat > "$MNT_ROOT/etc/NetworkManager/conf.d/99-usb0-unmanaged.conf" <<'CONF_EOF'
[keyfile]
unmanaged-devices=interface-name:usb0
CONF_EOF

log "writing usb0-static.service ($PI_ADDR)"
cat > "$MNT_ROOT/etc/systemd/system/usb0-static.service" <<SERVICE_EOF
[Unit]
Description=Static address on the USB ethernet gadget
After=systemd-modules-load.service
Before=network-pre.target
Wants=network-pre.target

[Service]
Type=oneshot
RemainAfterExit=yes
# usb0 only exists once the gadget module is loaded, which can be after this runs.
ExecStartPre=/bin/sh -c 'for i in \$(seq 1 30); do [ -d /sys/class/net/usb0 ] && exit 0; sleep 1; done; exit 1'
ExecStart=/sbin/ip link set usb0 up
ExecStart=/sbin/ip addr replace ${PI_ADDR} dev usb0

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# systemctl enable is just this symlink; we cannot run systemctl against another root.
mkdir -p "$MNT_ROOT/etc/systemd/system/multi-user.target.wants"
ln -sf /etc/systemd/system/usb0-static.service \
  "$MNT_ROOT/etc/systemd/system/multi-user.target.wants/usb0-static.service"
log "enabled usb0-static.service via multi-user.target.wants"

# Make sure ssh is on: the boot-partition flag is consumed on first boot.
if [[ -f "$MNT_ROOT/lib/systemd/system/ssh.service" ]]; then
  mkdir -p "$MNT_ROOT/etc/systemd/system/multi-user.target.wants"
  ln -sf /lib/systemd/system/ssh.service \
    "$MNT_ROOT/etc/systemd/system/multi-user.target.wants/ssh.service"
  log "ensured ssh.service is enabled"
fi

# ---------------------------------------------------------------- boot partition

CMDLINE="$MNT_BOOT/cmdline.txt"
cp "$CMDLINE" "$CMDLINE.bak"
line="$(tr -d '\n' < "$CMDLINE")"
line="$(sed 's| systemd\.run=[^ ]*||g; s| systemd\.run_success_action=[^ ]*||g; s| systemd\.unit=[^ ]*||g; s| console=ttyGS0,115200||g' <<<"$line")"
line="${line//modules-load=dwc2,g_serial/modules-load=dwc2,g_ether}"
[[ "$line" == *modules-load=dwc2,g_ether* ]] || line="$line modules-load=dwc2,g_ether"
printf '%s\n' "$line" > "$CMDLINE"
log "cleaned cmdline.txt:"
sed 's/^/    /' "$CMDLINE"

grep -q '^dtoverlay=dwc2,dr_mode=peripheral' "$MNT_BOOT/config.txt" \
  && log "config.txt already has dtoverlay=dwc2,dr_mode=peripheral" \
  || { printf '\n[all]\ndtoverlay=dwc2,dr_mode=peripheral\n' >> "$MNT_BOOT/config.txt"; log "added peripheral-mode overlay"; }

# Leave a breadcrumb the Pi itself can show us later.
date > "$MNT_ROOT/etc/gadget-fix-applied" 2>/dev/null || true

sync
log "done - unmounting"
cleanup
trap - EXIT

cat <<EOF

Card is ready. Put it back in the Zero, connect it to the Mac's USB port, and
after about a minute:

    ping -c3 ${PI_ADDR%/*}
    ssh <user>@${PI_ADDR%/*}

The Mac end should already be 10.55.0.2; if not:
    sudo networksetup -setmanual "Raspberry Pi USB Gadget" 10.55.0.2 255.255.255.0
EOF
