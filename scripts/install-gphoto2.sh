#!/usr/bin/env bash
#
# install-gphoto2.sh - install gphoto2 / libgphoto2 on a Raspberry Pi Zero
# so the ND Long Exposure Timer can drive a camera over USB.
#
# Two modes:
#   --apt     (default) install the distro packages. Fast (~1 min), but the
#             camera database is as old as your Raspberry Pi OS release.
#   --source  build the latest libgphoto2 + gphoto2 from the official release
#             tarballs. Needed for cameras newer than your distro knows about.
#             On a Pi Zero this takes 1-3 HOURS and wants swap. You have been warned.
#
# Both modes also:
#   - add you to the plugdev group,
#   - install/refresh the libgphoto2 udev rules,
#   - stop gvfs from grabbing the camera ("Could not claim the USB device").
#
# Usage: sudo ./install-gphoto2.sh [--apt|--source] [--user NAME] [--keep-gvfs] [-y]

set -euo pipefail

MODE="apt"
ASSUME_YES=0
FIX_GVFS=1
TARGET_USER="${SUDO_USER:-${USER:-pi}}"

# Overridable; empty means "ask GitHub for the latest release".
LIBGPHOTO2_VERSION="${LIBGPHOTO2_VERSION:-}"
GPHOTO2_VERSION="${GPHOTO2_VERSION:-}"

BUILD_DIR="/usr/local/src/gphoto2-build"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apt)       MODE="apt" ;;
    --source)    MODE="source" ;;
    --user)      TARGET_USER="${2:?--user needs a name}"; shift ;;
    --keep-gvfs) FIX_GVFS=0 ;;
    -y|--yes)    ASSUME_YES=1 ;;
    -h|--help)   usage ;;
    *)           die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

confirm() {
  [[ $ASSUME_YES -eq 1 ]] && return 0
  read -r -p "$1 [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

# ---------------------------------------------------------------- sanity checks

[[ $EUID -eq 0 ]] || die "run me with sudo: sudo $0 $*"
id "$TARGET_USER" >/dev/null 2>&1 || die "no such user: $TARGET_USER"

if [[ ! -f /etc/rpi-issue ]] && ! grep -qi raspberry /proc/device-tree/model 2>/dev/null; then
  warn "this does not look like a Raspberry Pi; continuing anyway"
fi

log "target user: $TARGET_USER   arch: $(uname -m)   mode: $MODE"

# ---------------------------------------------------------------- apt packages

export DEBIAN_FRONTEND=noninteractive

log "updating package lists"
apt-get update

if [[ "$MODE" == "apt" ]]; then
  log "installing gphoto2 from apt"
  apt-get install -y gphoto2 libgphoto2-6 libgphoto2-dev libgphoto2-port12 udev
else
  log "installing build dependencies"
  apt-get install -y \
    build-essential pkg-config autoconf automake libtool gettext \
    libltdl-dev libusb-1.0-0-dev libexif-dev libpopt-dev libjpeg-dev \
    libgd-dev libcurl4-openssl-dev libxml2-dev curl ca-certificates udev
fi

# ---------------------------------------------------------------- source build

latest_tag() { # repo -> version without leading v
  curl -fsSL "https://api.github.com/repos/gphoto/$1/releases/latest" \
    | sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' | head -n1
}

build_from_tarball() { # repo version
  local repo="$1" version="$2"
  local tarball="${repo}-${version}.tar.xz"
  local url="https://github.com/gphoto/${repo}/releases/download/v${version}/${tarball}"

  log "fetching $url"
  curl -fL --retry 3 -o "$BUILD_DIR/$tarball" "$url"

  rm -rf "${BUILD_DIR:?}/${repo}-${version}"
  tar -xJf "$BUILD_DIR/$tarball" -C "$BUILD_DIR"

  log "building ${repo} ${version} (this is the slow part)"
  (
    cd "$BUILD_DIR/${repo}-${version}"
    ./configure --prefix=/usr/local
    make -j"$(nproc)"
    make install
  )
}

if [[ "$MODE" == "source" ]]; then
  swap_kb=$(awk '/SwapTotal/ {print $2}' /proc/meminfo)
  if [[ "${swap_kb:-0}" -lt 524288 ]]; then
    warn "less than 512MB of swap ($((swap_kb / 1024))MB); the build may be OOM-killed."
    warn "raise CONF_SWAPSIZE in /etc/dphys-swapfile and 'systemctl restart dphys-swapfile' first."
    confirm "continue anyway?" || die "aborted"
  fi

  confirm "building from source can take several hours on a Pi Zero. Proceed?" || die "aborted"

  mkdir -p "$BUILD_DIR"

  [[ -n "$LIBGPHOTO2_VERSION" ]] || LIBGPHOTO2_VERSION="$(latest_tag libgphoto2)"
  [[ -n "$GPHOTO2_VERSION"    ]] || GPHOTO2_VERSION="$(latest_tag gphoto2)"
  [[ -n "$LIBGPHOTO2_VERSION" && -n "$GPHOTO2_VERSION" ]] \
    || die "could not resolve latest versions; set LIBGPHOTO2_VERSION and GPHOTO2_VERSION yourself"

  log "libgphoto2 $LIBGPHOTO2_VERSION, gphoto2 $GPHOTO2_VERSION"

  build_from_tarball libgphoto2 "$LIBGPHOTO2_VERSION"

  # gphoto2 links against the fresh libgphoto2 in /usr/local.
  echo /usr/local/lib > /etc/ld.so.conf.d/libgphoto2-local.conf
  ldconfig
  export PKG_CONFIG_PATH="/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH:-}"

  build_from_tarball gphoto2 "$GPHOTO2_VERSION"
  ldconfig

  if [[ -x /usr/bin/gphoto2 ]]; then
    warn "an apt-installed /usr/bin/gphoto2 is still present; /usr/local/bin comes first in PATH"
    warn "run 'apt-get remove gphoto2' if you want only the source build"
  fi
fi

# ---------------------------------------------------------------- device access

log "adding $TARGET_USER to the plugdev group"
groupadd -f plugdev
usermod -aG plugdev "$TARGET_USER"

print_camera_list="$(command -v print-camera-list || true)"
[[ -n "$print_camera_list" ]] || print_camera_list="$(find /usr/local/lib /usr/lib -name print-camera-list -type f 2>/dev/null | head -n1)"

if [[ -n "$print_camera_list" ]]; then
  log "generating udev rules from $print_camera_list"
  CAMLIBS="$(find /usr/local/lib /usr/lib -maxdepth 3 -type d -name 'vusb*' -path '*libgphoto2*' 2>/dev/null | head -n1)"
  [[ -n "$CAMLIBS" ]] && export CAMLIBS
  "$print_camera_list" udev-rules version 201 group plugdev mode 0660 \
    > /etc/udev/rules.d/90-libgphoto2.rules 2>/dev/null \
    || warn "could not generate udev rules; the packaged ones will have to do"
else
  log "using the udev rules shipped with the packages"
fi

udevadm control --reload-rules || true
udevadm trigger || true

# ---------------------------------------------------------------- gvfs kickout

# On Raspberry Pi OS Desktop, gvfs mounts the camera as a filesystem the moment
# it is plugged in, and gphoto2 then fails with "Could not claim the USB device".
# Masking the user services is reversible; purging gvfs is not, so we don't.
if [[ $FIX_GVFS -eq 1 ]]; then
  log "stopping gvfs from claiming the camera"
  for svc in gvfs-gphoto2-volume-monitor.service gvfs-mtp-volume-monitor.service; do
    if systemctl --user --machine="$TARGET_USER@" list-unit-files "$svc" >/dev/null 2>&1; then
      systemctl --user --machine="$TARGET_USER@" mask --now "$svc" 2>/dev/null \
        || warn "could not mask $svc for $TARGET_USER (fine on a headless/Lite install)"
    fi
  done
  for monitor in /usr/lib/gvfs/gvfs-gphoto2-volume-monitor \
                 /usr/libexec/gvfs-gphoto2-volume-monitor; do
    [[ -x "$monitor" ]] && chmod -x "$monitor" && log "disabled $monitor"
  done
  pkill -f gvfs-gphoto2-volume-monitor 2>/dev/null || true
fi

# ---------------------------------------------------------------- verify

log "installed: $(gphoto2 --version | head -n1)"
gphoto2 --version | sed -n '/libgphoto2 /p' | head -n2

log "looking for a camera"
if gphoto2 --auto-detect | tail -n +3 | grep -q .; then
  gphoto2 --auto-detect
  log "camera detected. Try: gphoto2 --set-config bulb=1 && sleep 30 && gphoto2 --set-config bulb=0"
else
  warn "no camera detected. Plug it in, switch it on, set it to PTP/MTP mode, and run: gphoto2 --auto-detect"
fi

cat <<EOF

Done.

Next steps:
  * Log out and back in (or reboot) so the plugdev group membership takes effect.
  * Sanity check:      gphoto2 --auto-detect
  * Camera abilities:  gphoto2 --abilities
  * Bulb exposure:     gphoto2 --set-config bulb=1; sleep N; gphoto2 --set-config bulb=0
    (Nikon bodies often want --set-config eosremoterelease / bulb depending on model;
     'gphoto2 --list-config' shows what your body actually exposes.)

If you still get "Could not claim the USB device", something else has the camera:
  ps aux | grep -e gvfs -e gphoto
EOF
