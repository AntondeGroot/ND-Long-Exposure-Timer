#!/bin/bash
# Runs ONCE on the Pi, early in boot, via systemd.run= in cmdline.txt.
# Installed on the boot partition by enable-wifi.sh.
#
# Joins the Wi-Fi network and authorizes an ssh key, so the Pi can be reached
# without the USB link. NetworkManager is not running this early, so its
# connection file is written directly rather than through nmcli.

set +e   # a failure here must never leave the Pi unbootable

BOOT=/boot/firmware
[ -d "$BOOT" ] || BOOT=/boot

CREDENTIALS="$BOOT/wifi-credentials"
SSH_KEY="$BOOT/wifi-authorized-key.pub"
CONNECTION=/etc/NetworkManager/system-connections/nd-wifi.nmconnection
UNBLOCK_UNIT=/etc/systemd/system/nd-wifi-unblock.service
FIRST_USER_UID=1000

# Beats the metric 500 default route usb0-static.service adds through the Mac,
# which goes nowhere unless the Mac is sharing its connection.
WIFI_ROUTE_METRIC=100

log() { echo "[wifi] $*" | tee -a "$BOOT/wifi-setup.log"; }

keyfile_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g'; }

write_wifi_connection() {
  local ssid password
  { IFS= read -r ssid; IFS= read -r password; } < "$CREDENTIALS"
  if [ -z "$ssid" ] || [ -z "$password" ]; then
    log "WARNING: $CREDENTIALS is missing or incomplete - not configuring Wi-Fi"
    return
  fi

  mkdir -p "$(dirname "$CONNECTION")"
  ( umask 077
    cat > "$CONNECTION" <<CONNECTION_EOF
[connection]
id=nd-wifi
type=wifi
interface-name=wlan0
autoconnect=true

[wifi]
mode=infrastructure
ssid=$(keyfile_escape "$ssid")

[wifi-security]
key-mgmt=wpa-psk
psk=$(keyfile_escape "$password")

[ipv4]
method=auto
route-metric=$WIFI_ROUTE_METRIC

[ipv6]
method=auto
CONNECTION_EOF
  )
  chmod 600 "$CONNECTION"
  log "wrote the Wi-Fi connection for '$ssid'"
}

# Pi OS ships with Wi-Fi off in two places: an rfkill soft block, and
# WirelessEnabled=false in NetworkManager's own state file, which makes it put
# the block straight back. Clearing the rfkill block alone leaves wlan0
# "unavailable", so ask NetworkManager itself, once it is up. It saves the answer.
keep_wifi_unblocked() {
  cat > "$UNBLOCK_UNIT" <<'UNIT_EOF'
[Unit]
Description=Turn Wi-Fi on once NetworkManager is running
After=NetworkManager.service systemd-rfkill.service
Wants=NetworkManager.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=rfkill unblock wifi
ExecStart=nmcli radio wifi on

[Install]
WantedBy=multi-user.target
UNIT_EOF

  if systemctl enable nd-wifi-unblock.service >/dev/null 2>&1; then
    log "enabled nd-wifi-unblock.service"
  else
    log "WARNING: could not enable nd-wifi-unblock.service"
  fi
}

# The account name is whatever the card was flashed with, so find it here,
# where /etc/passwd is readable, rather than trusting a guess from the Mac.
authorize_ssh_key() {
  local account home
  account="$(getent passwd "$FIRST_USER_UID" | cut -d: -f1)"
  home="$(getent passwd "$FIRST_USER_UID" | cut -d: -f6)"
  if [ -z "$account" ] || [ ! -f "$SSH_KEY" ]; then
    log "WARNING: no account with uid $FIRST_USER_UID or no key - ssh key not installed"
    return
  fi

  mkdir -p "$home/.ssh"
  touch "$home/.ssh/authorized_keys"
  grep -qxFf "$SSH_KEY" "$home/.ssh/authorized_keys" \
    || cat "$SSH_KEY" >> "$home/.ssh/authorized_keys"
  chmod 700 "$home/.ssh"
  chmod 600 "$home/.ssh/authorized_keys"
  chown -R "$account:" "$home/.ssh"
  log "authorized the ssh key for $account"
}

remove_boot_hook() {
  [ -f "$BOOT/cmdline.txt" ] || return
  cp "$BOOT/cmdline.txt" "$BOOT/cmdline.txt.wifi.bak"
  sed -i 's| systemd\.run=[^ ]*||g; s| systemd\.run_success_action=[^ ]*||g; s| systemd\.unit=[^ ]*||g' "$BOOT/cmdline.txt"
  log "removed the boot hook from cmdline.txt"
}

log "starting at $(date 2>/dev/null)"
write_wifi_connection
keep_wifi_unblocked
authorize_ssh_key
systemctl enable ssh >/dev/null 2>&1 && log "ssh enabled"
remove_boot_hook

# The boot partition is readable by anything with a card slot.
rm -f "$CREDENTIALS"
log "removed the Wi-Fi credentials from the boot partition"

sync
log "done - rebooting into the normal system"
exit 0
