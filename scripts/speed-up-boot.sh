#!/usr/bin/env bash
#
# speed-up-boot.sh - stop the Pi waiting for things this device does not have.
#
# The camera timer is switched on in the field and wanted immediately, so boot
# time is a feature. Most of what a stock Raspberry Pi OS waits for is irrelevant
# here: there is no wifi, no Bluetooth radio on a plain Zero, no modem, and the
# only "network" is a USB cable to a laptop that is usually not attached.
#
# Everything here is reversible, and the script prints how. Nothing that could
# cost you access to the device is disabled by default.
#
# Usage (on the Pi):
#   sudo ./speed-up-boot.sh --measure     just report, change nothing
#   sudo ./speed-up-boot.sh               disable the safe set
#   sudo ./speed-up-boot.sh --aggressive  also drop avahi and swap
#   sudo ./speed-up-boot.sh --no-unused-hardware
#                                         also stop probing the camera, display
#                                         and audio hardware this device has not
#                                         got. Costs you the HDMI console.
#   sudo ./speed-up-boot.sh --trim-firmware
#                                         work on the stage before the kernel:
#                                         drop the 14MB initramfs, stop the HDMI
#                                         and HAT-EEPROM probes, quieten the
#                                         kernel log. Measured elsewhere at ~2s
#                                         of probing plus whatever 14MB of SD
#                                         reads costs on an ARMv6.
#   sudo ./speed-up-boot.sh --restore     re-enable everything it disabled

set -euo pipefail

STATE_FILE="/var/lib/nd-timer-boot-disabled"

# Bookworm moved the firmware config; older releases keep it in /boot.
CONFIG_TXT="/boot/firmware/config.txt"
[[ -f "$CONFIG_TXT" ]] || CONFIG_TXT="/boot/config.txt"

TRIM_HARDWARE=0
TRIM_FIRMWARE=0

# cloud-init is disabled with a flag file rather than by masking its five units -
# that is the supported way, and it survives a cloud-init package upgrade putting
# the units back.
CLOUD_INIT_FLAG="/etc/cloud/cloud-init.disabled"

# Hardware the stock config.txt switches on and this device does not have. Each
# of these costs module loads in the busiest part of the boot: measured on this
# card, the camera stack alone (bcm2835_codec, bcm2835_isp, mmal_vchiq, v4l2,
# videodev, videobuf2_*) accounted for over seven seconds between two consecutive
# kernel messages, and the log carries "[drm] Cannot find any crtc or sizes"
# twice for a display that is not attached.
#
# The lines are commented out in place rather than overridden by later ones,
# because a dtoverlay cannot be taken back: "dtoverlay=vc4-kms-v3d" earlier in
# the file wins whatever follows it.
UNUSED_HARDWARE=(
  'dtoverlay=vc4-kms-v3d'
  'max_framebuffers=2'
  'display_auto_detect=1'
  'camera_auto_detect=1'
  'dtparam=audio=on'
)

# What --restore looks for. Kept verbose on purpose: someone reading config.txt
# on a card in a reader, wondering why their HDMI is dead, should be able to
# guess what did it and how to undo it.
OFF_MARKER='#nd-timer-off# '

CMDLINE_TXT="$(dirname "$CONFIG_TXT")/cmdline.txt"
CMDLINE_BACKUP="/var/lib/nd-timer-cmdline.bak"

# Lines added to config.txt as a block, so --restore can lift the whole block out
# again. The firmware reads these before the kernel exists, which is a stage
# nothing on the Pi itself can measure.
FIRMWARE_BEGIN='#nd-timer-firmware-begin#'
FIRMWARE_END='#nd-timer-firmware-end#'

# auto_initramfs=1 cannot be overridden by a later line, so it is commented out
# with OFF_MARKER like the hardware lines.
INITRAMFS_LINE='auto_initramfs=1'

# What the kernel log costs when every line goes to a serial console at 115200.
QUIET_WORDS='quiet loglevel=3'

# The panel's bus, as kernel module names. Loaded from cmdline.txt because the
# initramfs that used to load them is what --trim-firmware removes.
SPI_MODULES='spi_bcm2835,spidev'

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Everything below this line assumes the Pi. Run on the Mac, these commands
# either do not exist or aim at the wrong machine - a reboot meant for the timer
# restarts the laptop - so refuse outright instead of half-running.
[[ "$(uname -s)" == "Linux" ]] || die "run this on the Pi, not here (this is $(uname -s))"

# Waiting for a network that is a USB cable to a laptop is the classic Pi boot
# delay - these can each cost 15-30s and buy this device nothing.
SAFE_TO_DISABLE=(
  NetworkManager-wait-online.service
  systemd-networkd-wait-online.service
  # A plain Zero has no Bluetooth radio at all.
  bluetooth.service
  hciuart.service
  # No modem, no cellular anything.
  ModemManager.service
  # A hotkey daemon for input devices we drive ourselves through gpiozero.
  triggerhappy.service
  triggerhappy.socket
  # Loads a console keymap for a keyboard this device does not have - 3.5s in
  # blame, 2026-09-29, and ordered before local-fs-pre.target, so on the way to
  # the filesystems. A keyboard plugged in later gets the default layout; the
  # serial console does not use it.
  keyboard-setup.service
  # The rest are not on the way to the first screen - multi-user.target starts
  # at ~35s, after the device is ready at ~25s - so they buy no boot time. They
  # go because they are useless on this hardware and cost CPU later, when the
  # timer is in use: a Zero has one core, and a background job waking during an
  # exposure competes with it.
  #
  # Wi-Fi. A plain Zero has no radio.
  wpa_supplicant.service
  # Updates the boot EEPROM of a Pi 4 or 5. A Zero has none. 3s a boot.
  rpi-eeprom-update.service
  # Package lists and upgrades, on a device with no internet of its own. When
  # they do run on a Zero they take minutes of CPU. apt still works by hand.
  apt-daily.timer
  apt-daily-upgrade.timer
  # Rebuilds the man page index - the same kind of surprise, for nothing.
  man-db.timer
  # ext4 metadata checks on LVM snapshots. There is no LVM here.
  e2scrub_all.timer
  e2scrub_reap.service
)

# timesyncd, started 90s after boot instead of during it. It cannot sync here -
# there is no network unless the Mac shares one - but it keeps the clock honest
# anyway: with no RTC, PID 1 starts each boot from the time timesyncd last saved
# in /var/lib/systemd/timesync/clock, and when the Mac does share a connection it
# corrects the clock. Disabled outright, every boot would restart from the same
# stale moment. Delayed, it still does both, and takes its 3.9s (blame,
# 2026-09-29) out of the part of the boot the application is competing for.
LATE_TIMESYNC_TIMER="/etc/systemd/system/nd-timer-late-timesync.timer"

# Useful but not free. avahi is what answers raspberrypi.local, and the device
# has a static address, but losing it removes a way back in if that ever breaks.
AGGRESSIVE_EXTRAS=(
  avahi-daemon.service
  avahi-daemon.socket
  dphys-swapfile.service
)

# Static units: no [Install] section, so they can only be masked.
#
# rpi-resize-swap-file spends 19s a boot sizing /var/swap - measured - and on
# this image nothing ever turns that file into swap: dphys-swapfile.service is
# not installed and swapon reports nothing. Nineteen seconds and 426MB of card
# for a file the kernel never reads. --restore unmasks it.
MASK_BY_DEFAULT=(
  rpi-resize-swap-file.service
)

# Generators run before systemd starts a single unit, so their time is added to
# everything - the splash, udev, the application. Measured 2026-09-29: systemd
# spent 10.6s in generators, and rpi-swap-generator is the one that costs. It
# reads its config through a Python script (1.1s warm) and then sizes a swap file
# and a zram device through two shell scripts (2.3s each, warm), every boot, for
# swap this device does not use: swap is 0 on it, and the application runs in
# ~95MB of 427MB. Every other generator here took about 0.1s.
#
# Masked the way systemd documents: a symlink to /dev/null of the same name in
# /etc/systemd/system-generators. Mechanism=none in swap.conf would skip the two
# sizings but still pay for the Python config read. --restore removes the link.
MASK_GENERATORS=(
  rpi-swap-generator
)
GENERATOR_MASK_DIR="/etc/systemd/system-generators"

# cloud-init exists to configure a machine from a cloud provider's metadata
# service. This is a camera timer. It still costs the better part of a minute:
# on a measured boot here, cloud-init-main took 19s and sysinit.target waited on
# cloud-init-network until 59s, so almost the whole userspace boot sat behind it.
#
# It is only safe to do this AFTER the first boot. Pi OS seeds it from the boot
# partition (DataSourceNoCloud, seed=file:///boot/firmware), which is part of how
# a freshly flashed card sets itself up - so flash-sd.sh must not do this, and
# setup-pi.sh, which runs later, can.
disable_cloud_init() {
  [[ -d /etc/cloud ]] || return 0
  # An explicit if, not "[[ -e ... ]] && return": under set -e that reads as an
  # early return but its exit status is the test's, which makes the function
  # look failed to a caller that checks.
  if [[ -e "$CLOUD_INIT_FLAG" ]]; then
    return 0
  fi
  touch "$CLOUD_INIT_FLAG"
  printf '    disabled cloud-init (%s)\n' "$CLOUD_INIT_FLAG"
}

# NetworkManager is the biggest single item on this device's critical path:
# measured at 21s, of which 12s was NM blocked behind a systemd daemon-reload
# that netplan triggers. And it manages nothing - usb0 is unmanaged by a conf.d
# drop-in and addressed by usb0-static.service with plain ip commands, lo is the
# kernel's, and resolv.conf is a static file.
#
# That is true of THIS device, not of Pis in general: on one with wifi, disabling
# NetworkManager removes networking and quite possibly your way back in. So the
# preconditions are checked rather than assumed, and it declines out loud.
network_manager_is_doing_nothing() {
  local wireless managed

  # Any wireless hardware at all, configured or not.
  if [[ -n "$(ls -d /sys/class/net/*/wireless 2>/dev/null)" ]] \
     || [[ -n "$(ls /sys/class/ieee80211 2>/dev/null)" ]]; then
    warn "wifi hardware present - leaving NetworkManager alone"
    return 1
  fi

  # Any device NM actually manages, loopback aside.
  if command -v nmcli >/dev/null 2>&1; then
    managed="$(nmcli -t -f DEVICE,STATE device status 2>/dev/null \
               | grep -v "^lo:" | grep -cv ":unmanaged$" || true)"
    if [[ "${managed:-0}" -gt 0 ]]; then
      warn "NetworkManager is managing $managed device(s) - leaving it alone"
      return 1
    fi
  fi

  # If something points resolv.conf at NM, DNS goes with it.
  if [[ -L /etc/resolv.conf ]] && readlink /etc/resolv.conf | grep -qi "NetworkManager"; then
    warn "resolv.conf is managed by NetworkManager - leaving it alone"
    return 1
  fi

  return 0
}

disable_unused_hardware() {
  local line disabled=0

  [[ -f "$CONFIG_TXT" ]] || { warn "no config.txt found - not trimming hardware"; return; }

  for line in "${UNUSED_HARDWARE[@]}"; do
    grep -qxF "$line" "$CONFIG_TXT" || continue
    sed -i "s|^${line}\$|${OFF_MARKER}${line}|" "$CONFIG_TXT"
    printf '    commented out %s\n' "$line"
    disabled=1
  done

  if [[ $disabled -eq 0 ]]; then
    printf '    nothing to do - already trimmed\n'
  else
    warn "no HDMI console after this reboot. ssh over USB and the serial console"
    warn "are the ways in; see enable-serial-console.sh."
  fi
}

restore_unused_hardware() {
  [[ -f "$CONFIG_TXT" ]] || return 0
  grep -q "^${OFF_MARKER}" "$CONFIG_TXT" || return 0
  sed -i "s|^${OFF_MARKER}||" "$CONFIG_TXT"
  printf '    restored the hardware lines in %s\n' "$CONFIG_TXT"
}

trim_firmware() {
  [[ -f "$CONFIG_TXT" ]] || { warn "no config.txt found - not trimming firmware"; return; }

  if grep -qxF "$INITRAMFS_LINE" "$CONFIG_TXT"; then
    sed -i "s|^${INITRAMFS_LINE}\$|${OFF_MARKER}${INITRAMFS_LINE}|" "$CONFIG_TXT"
    printf '    commented out %s (the firmware was loading a 14MB initramfs)\n' "$INITRAMFS_LINE"
  fi

  if ! grep -qF "$FIRMWARE_BEGIN" "$CONFIG_TXT"; then
    {
      # No blank line before the marker: --restore deletes from the marker to the
      # end marker, and a blank line outside that range would survive the round
      # trip. The markers are comments, so the file reads well enough without it.
      echo "$FIRMWARE_BEGIN"
      echo "# Managed by speed-up-boot.sh --trim-firmware; --restore removes this block."
      echo "#"
      echo "# Probes for hardware that is not attached, paid for before the kernel"
      echo "# starts. Measured at ~1.5s for the EDID read and ~0.5s for the HAT,"
      echo "# PoE and LCD detection by kittenlabs.de on a Zero 2 W."
      echo "hdmi_ignore_edid=0xa5000080"
      echo "hdmi_blanking=2"
      echo "force_eeprom_read=0"
      echo "disable_poe_fan=1"
      echo "ignore_lcd=1"
      echo "$FIRMWARE_END"
    } >> "$CONFIG_TXT"
    printf '    stopped the HDMI, HAT, PoE and LCD probes\n'
  fi

  # The serial console is a way back in and stays; what goes is the volume of
  # what is written to it, which at 115200 baud is not free.
  if [[ -f "$CMDLINE_TXT" ]] && ! grep -qw quiet "$CMDLINE_TXT"; then
    [[ -f "$CMDLINE_BACKUP" ]] || cp "$CMDLINE_TXT" "$CMDLINE_BACKUP"
    sed -i "1s|\$| ${QUIET_WORDS}|" "$CMDLINE_TXT"
    printf '    added "%s" to cmdline.txt (backup at %s)\n' "$QUIET_WORDS" "$CMDLINE_BACKUP"
  fi

  # Dropping the initramfs takes the SPI modules with it, which is not obvious
  # until the panel stops working: spi_bcm2835 and spidev are modules, the
  # initramfs was loading them, and without it they wait for udev's coldplug
  # pass. Measured: /dev/spidev0.0 did not appear within the splash's 20s.
  #
  # modules-load= is handled by the kernel itself, long before udev, which is
  # earlier than the initramfs managed anyway.
  if [[ -f "$CMDLINE_TXT" ]] && ! grep -q "$SPI_MODULES" "$CMDLINE_TXT"; then
    [[ -f "$CMDLINE_BACKUP" ]] || cp "$CMDLINE_TXT" "$CMDLINE_BACKUP"
    if grep -q "modules-load=" "$CMDLINE_TXT"; then
      sed -i "1s|\(modules-load=[^ ]*\)|\1,${SPI_MODULES}|" "$CMDLINE_TXT"
    else
      sed -i "1s|\$| modules-load=${SPI_MODULES}|" "$CMDLINE_TXT"
    fi
    printf '    added %s to modules-load (the initramfs used to load these)\n' "$SPI_MODULES"
  fi

  warn "the initramfs is gone after this reboot. If the Pi does not come back, put"
  warn "auto_initramfs=1 back with the card in a reader - it is one commented line."
}

restore_firmware_trim() {
  [[ -f "$CONFIG_TXT" ]] || return 0

  if grep -qF "$FIRMWARE_BEGIN" "$CONFIG_TXT"; then
    sed -i "/^${FIRMWARE_BEGIN}\$/,/^${FIRMWARE_END}\$/d" "$CONFIG_TXT"
    printf '    removed the firmware block from %s\n' "$CONFIG_TXT"
  fi

  if [[ -f "$CMDLINE_BACKUP" ]]; then
    cp "$CMDLINE_BACKUP" "$CMDLINE_TXT"
    rm -f "$CMDLINE_BACKUP"
    printf '    restored cmdline.txt\n'
  fi
}

measure() {
  log "boot time"
  systemd-analyze 2>/dev/null | sed 's/^/    /' || warn "systemd-analyze unavailable"
  echo
  log "slowest units"
  systemd-analyze blame 2>/dev/null | head -15 | sed 's/^/    /' || true
  echo
  log "critical chain"
  systemd-analyze critical-chain 2>/dev/null | head -12 | sed 's/^/    /' || true
}

# A "static" unit has no [Install] section, so systemctl disable fails on it and
# does nothing - silently, which is worse. Masking is the only way to stop one.
# Recorded with a prefix so --restore knows to unmask rather than enable.
mask_units() {
  local unit
  for unit in "$@"; do
    systemctl list-unit-files "$unit" >/dev/null 2>&1 || continue
    [[ "$(systemctl is-enabled "$unit" 2>/dev/null)" == "masked" ]] && continue
    if systemctl mask "$unit" >/dev/null 2>&1; then
      echo "mask:$unit" >> "$STATE_FILE"
      printf '    masked %s\n' "$unit"
    fi
  done
}

mask_generators() {
  local name link
  mkdir -p "$GENERATOR_MASK_DIR"
  for name in "$@"; do
    [[ -e "/usr/lib/systemd/system-generators/$name" ]] || continue
    link="$GENERATOR_MASK_DIR/$name"
    [[ "$(readlink "$link" 2>/dev/null)" == /dev/null ]] && continue
    if [[ -e "$link" || -L "$link" ]]; then
      warn "$link already exists and is not a mask; leaving it alone"
      continue
    fi
    ln -s /dev/null "$link"
    echo "generator:$name" >> "$STATE_FILE"
    printf '    masked generator %s\n' "$name"
  done
}

delay_timesyncd() {
  [[ -f /usr/lib/systemd/system/systemd-timesyncd.service ]] || return 0
  if [[ -f "$LATE_TIMESYNC_TIMER" ]]; then
    return 0
  fi
  cat > "$LATE_TIMESYNC_TIMER" <<'TIMER_EOF'
# Written by speed-up-boot.sh; --restore removes it and re-enables timesyncd.
[Unit]
Description=Start timesyncd once the boot is over
# Without this a timer is ordered after sysinit.target and before the service it
# starts - and timesyncd orders itself before sysinit.target. A cycle, which
# systemd would break by dropping the start.
DefaultDependencies=no

[Timer]
OnBootSec=90
Unit=systemd-timesyncd.service

[Install]
WantedBy=timers.target
TIMER_EOF
  systemctl disable systemd-timesyncd.service >/dev/null 2>&1 || true
  systemctl enable "$(basename "$LATE_TIMESYNC_TIMER")" >/dev/null 2>&1
  echo "late-timesync" >> "$STATE_FILE"
  printf '    timesyncd now starts 90s after boot\n'
}

disable_units() {
  local unit
  for unit in "$@"; do
    if ! systemctl list-unit-files "$unit" >/dev/null 2>&1; then
      continue
    fi
    if [[ "$(systemctl is-enabled "$unit" 2>/dev/null)" == "masked" ]]; then
      continue
    fi
    if systemctl disable --now "$unit" >/dev/null 2>&1; then
      echo "$unit" >> "$STATE_FILE"
      printf '    disabled %s\n' "$unit"
    fi
  done
}

if [[ "${1:-}" == "--no-unused-hardware" ]]; then
  TRIM_HARDWARE=1
  shift
fi

if [[ "${1:-}" == "--trim-firmware" ]]; then
  TRIM_FIRMWARE=1
  shift
fi

[[ "${1:-}" == "--measure" ]] && { measure; exit 0; }
[[ $EUID -eq 0 ]] || die "run with sudo"

if [[ "${1:-}" == "--restore" ]]; then
  [[ -f "$STATE_FILE" ]] || die "nothing recorded as disabled"
  log "re-enabling what this script disabled"
  while read -r unit; do
    [[ -n "$unit" ]] || continue
    if [[ "$unit" == mask:* ]]; then
      unit="${unit#mask:}"
      systemctl unmask "$unit" >/dev/null 2>&1 && printf '    unmasked %s\n' "$unit"
    elif [[ "$unit" == late-timesync ]]; then
      systemctl disable "$(basename "$LATE_TIMESYNC_TIMER")" >/dev/null 2>&1 || true
      rm -f "$LATE_TIMESYNC_TIMER"
      systemctl enable systemd-timesyncd.service >/dev/null 2>&1 \
        && printf '    timesyncd starts with the boot again\n'
    elif [[ "$unit" == generator:* ]]; then
      unit="${unit#generator:}"
      # Only ever a link this script made: one to /dev/null.
      if [[ "$(readlink "$GENERATOR_MASK_DIR/$unit" 2>/dev/null)" == /dev/null ]]; then
        rm -f "$GENERATOR_MASK_DIR/$unit" && printf '    unmasked generator %s\n' "$unit"
      fi
    else
      systemctl enable "$unit" >/dev/null 2>&1 && printf '    enabled %s\n' "$unit"
    fi
  done < "$STATE_FILE"
  rm -f "$STATE_FILE"
  if [[ -e "$CLOUD_INIT_FLAG" ]]; then
    rm -f "$CLOUD_INIT_FLAG"
    printf '    enabled cloud-init\n'
  fi
  restore_unused_hardware
  restore_firmware_trim
  log "reboot to apply"
  exit 0
fi

measure
echo
log "disabling services this device has no use for"
mkdir -p "$(dirname "$STATE_FILE")"
disable_units "${SAFE_TO_DISABLE[@]}"
mask_units "${MASK_BY_DEFAULT[@]}"
mask_generators "${MASK_GENERATORS[@]}"
delay_timesyncd
disable_cloud_init

if network_manager_is_doing_nothing; then
  disable_units NetworkManager.service NetworkManager-dispatcher.service
fi

if [[ "${1:-}" == "--aggressive" ]]; then
  warn "also dropping avahi (no more .local name) and swap"
  disable_units "${AGGRESSIVE_EXTRAS[@]}"
fi

# The bootloader's own pause, before Linux starts at all.
if [[ -f "$CONFIG_TXT" ]] && ! grep -q '^boot_delay=0' "$CONFIG_TXT"; then
  printf '\n# No reason to pause before starting the kernel.\nboot_delay=0\n' >> "$CONFIG_TXT"
  log "set boot_delay=0 in $CONFIG_TXT"
fi

if [[ $TRIM_HARDWARE -eq 1 ]]; then
  log "stopping the probe of hardware this device has not got"
  disable_unused_hardware
fi

if [[ $TRIM_FIRMWARE -eq 1 ]]; then
  log "trimming the stage before the kernel"
  trim_firmware
fi

if [[ $TRIM_HARDWARE -eq 1 ]]; then
  TRIM_HINT=""
else
  TRIM_HINT="Not yet trimmed: the camera, display and audio hardware this device has not
got, which costs module loads in the busiest part of the boot. Add it with

    sudo $0 --no-unused-hardware

"
fi

cat <<EOF

Done. Reboot, then compare:

    sudo systemctl reboot
    ./speed-up-boot.sh --measure

${TRIM_HINT}To put everything back:  sudo $0 --restore
EOF
