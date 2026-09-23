#!/bin/bash
# Runs ONCE on the Pi, early in boot, via systemd.run= in cmdline.txt.
# Installed on the boot partition by enable-gadget-network.sh.
#
# Bookworm's NetworkManager leaves usb0 unconfigured, and with no DHCP server on
# the host the interface never comes up - so the ethernet gadget reports no
# carrier and the Mac sees a dead link. This gives usb0 a fixed address of its
# own, independent of NetworkManager, and removes its own boot hook afterwards.

set +e   # a failure here must never leave the Pi unbootable

PI_ADDR="10.55.0.1/24"
MAC_ADDR="10.55.0.2"

BOOT=/boot/firmware
[ -d "$BOOT" ] || BOOT=/boot

log() { echo "[gadget-network] $*" | tee -a "$BOOT/gadget-setup.log"; }

log "starting at $(date 2>/dev/null)"

# Keep NetworkManager away from usb0 so it cannot flush the static address.
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/99-usb0-unmanaged.conf <<'CONF_EOF'
[keyfile]
unmanaged-devices=interface-name:usb0
CONF_EOF
log "told NetworkManager to ignore usb0"

# usb0 only exists once systemd-modules-load has pulled in the gadget driver,
# which can land after this unit would otherwise run - hence the wait.
cat > /etc/systemd/system/usb0-static.service <<SERVICE_EOF
[Unit]
Description=Static address on the USB ethernet gadget
After=systemd-modules-load.service
Wants=network-pre.target
Before=network-pre.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=/bin/sh -c 'for i in \$(seq 1 30); do [ -d /sys/class/net/usb0 ] && exit 0; sleep 1; done; echo "usb0 never appeared"; exit 1'
ExecStart=/sbin/ip link set usb0 up
ExecStart=/sbin/ip addr replace ${PI_ADDR} dev usb0
# A default route out through the Mac, for the one thing this Pi cannot do
# without: apt and pip during setup-pi.sh. It only carries traffic while the
# Mac is actually sharing its connection (scripts/share-internet-macos.sh);
# the rest of the time it is a route to nowhere, which costs nothing on a
# machine that has no other network. The metric keeps it out of the way of
# anything better that turns up later.
ExecStart=/sbin/ip route replace default via ${MAC_ADDR} dev usb0 metric 500

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl enable usb0-static.service >/dev/null 2>&1 \
  && log "enabled usb0-static.service (${PI_ADDR})" \
  || log "WARNING: could not enable usb0-static.service"

# Make sure ssh is really on - the boot-partition flag file is consumed on the
# first boot, so re-enabling here is harmless and covers the case where it was not.
systemctl enable ssh >/dev/null 2>&1 && log "ssh enabled"

# Strip this script's own hooks so the next boot is a normal one.
if [ -f "$BOOT/cmdline.txt" ]; then
  cp "$BOOT/cmdline.txt" "$BOOT/cmdline.txt.firstrun.bak"
  sed -i 's| systemd\.run=[^ ]*||g; s| systemd\.run_success_action=[^ ]*||g; s| systemd\.unit=[^ ]*||g' "$BOOT/cmdline.txt"
  log "removed the firstrun hooks from cmdline.txt"
fi

sync
log "done - rebooting into the normal system"
exit 0
