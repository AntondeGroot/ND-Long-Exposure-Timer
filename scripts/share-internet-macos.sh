#!/usr/bin/env bash
#
# share-internet-macos.sh - give the Pi internet over the USB link.
#
# macOS Internet Sharing cannot be used here: it takes over the gadget interface,
# renumbers it to 192.168.2.1 and runs a DHCP server, while the Pi holds a static
# 10.55.0.1 with NetworkManager told to ignore usb0 - so it would never take a
# lease, and we would lose the link. This does the same job with pf, keeping the
# addressing we already have.
#
# Usage: sudo ./share-internet-macos.sh [--off] [--uplink en0]

set -euo pipefail

SUBNET="10.55.0.0/24"
UPLINK="en0"
ANCHOR="/etc/pf.anchors/nd-timer-nat"
# /etc/pf.conf only references anchors under "com.apple/*", so a top-level anchor
# of our own would load without ever being evaluated. Nesting under that wildcard
# gets the rule applied without editing any system file.
ANCHOR_NAME="com.apple/nd-timer-nat"
OFF=0

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --off)     OFF=1 ;;
    --uplink)  UPLINK="${2:?--uplink needs an interface}"; shift ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)         die "unknown option: $1" ;;
  esac
  shift
done

[[ $EUID -eq 0 ]] || die "run with sudo: sudo $0 $*"

if [[ $OFF -eq 1 ]]; then
  log "disabling NAT"
  sysctl -w net.inet.ip.forwarding=0 >/dev/null
  pfctl -a "$ANCHOR_NAME" -F nat 2>/dev/null || true
  rm -f "$ANCHOR"
  log "done - the Pi keeps the link but loses internet"
  exit 0
fi

ifconfig "$UPLINK" >/dev/null 2>&1 || die "no such uplink interface: $UPLINK"
UPLINK_IP="$(ipconfig getifaddr "$UPLINK" 2>/dev/null || true)"
[[ -n "$UPLINK_IP" ]] || die "$UPLINK has no address - is it the interface with internet?"

log "uplink $UPLINK ($UPLINK_IP), sharing to $SUBNET"

sysctl -w net.inet.ip.forwarding=1 >/dev/null
log "enabled IPv4 forwarding"

cat > "$ANCHOR" <<ANCHOR_EOF
nat on $UPLINK from $SUBNET to any -> ($UPLINK)
ANCHOR_EOF

# Load our rule into its own anchor so the system ruleset is left alone.
pfctl -E >/dev/null 2>&1 || true
pfctl -a "$ANCHOR_NAME" -f "$ANCHOR"
log "loaded NAT rule into the $ANCHOR_NAME anchor"

log "active NAT rules:"
pfctl -a "$ANCHOR_NAME" -s nat 2>/dev/null | sed 's/^/    /'

cat <<EOF

NAT is up. On the Pi, add a default route through this Mac:

    sudo ip route add default via 10.55.0.2 dev usb0

To make it permanent there, the usb0-static.service already owns the interface,
so adding the route to that unit is the tidy place for it.

Turn this off again with:  sudo $0 --off
Note: this does not survive a reboot of the Mac.
EOF
