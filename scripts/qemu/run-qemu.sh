#!/usr/bin/env bash
set -euo pipefail

TOPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

resolve_default_build_dir() {
  if [[ -d "${TOPDIR}/builds/conf" ]]; then
    echo "${TOPDIR}/builds"
  elif [[ -d "${TOPDIR}/build/conf" ]]; then
    echo "${TOPDIR}/build"
  elif [[ -d "${TOPDIR}/builds" ]]; then
    echo "${TOPDIR}/builds"
  else
    echo "${TOPDIR}/builds"
  fi
}

BUILD_DIR="${BUILD_DIR:-$(resolve_default_build_dir)}"
MACHINE="${MACHINE:-qemux86-64}"
IMAGE="${IMAGE:-tuxbox-qemu-image}"
FSTYPE="${FSTYPE:-wic}"
RUNQEMU="${RUNQEMU:-${TOPDIR}/poky/scripts/runqemu}"
QEMU_STATIC_RES="${QEMU_STATIC_RES:-1280x720}"
QEMU_NET_MODE="${QEMU_NET_MODE:-auto}"
QEMU_BRIDGE_NAME="${QEMU_BRIDGE_NAME:-br0}"

if [[ ! -x "${RUNQEMU}" ]]; then
  echo "runqemu not found at ${RUNQEMU}" >&2
  exit 1
fi

if [[ ! -d "${BUILD_DIR}/conf" ]]; then
  echo "Build config not found in ${BUILD_DIR}/conf." >&2
  echo "Run: ./cli.py config --machine ${MACHINE} or make config MACHINE=${MACHINE}" >&2
  exit 1
fi

DEPLOY_DIR="${BUILD_DIR}/tmp/deploy/images/${MACHINE}"

CONF_MACHINE="${BUILD_DIR}/conf/local.conf.${MACHINE}.inc"
if [[ -f "${CONF_MACHINE}" ]]; then
  tmpdir_line="$(sed -n 's/^TMPDIR = \"\(.*\)\"/\1/p' "${CONF_MACHINE}" | head -n 1)"
  if [[ -n "${tmpdir_line}" ]]; then
    tmpdir="${tmpdir_line}"
    tmpdir="${tmpdir//\$\{TOPDIR\}/${BUILD_DIR}}"
    tmpdir="${tmpdir//\$\{MACHINE\}/${MACHINE}}"
    if [[ -d "${tmpdir}/deploy/images/${MACHINE}" ]]; then
      DEPLOY_DIR="${tmpdir}/deploy/images/${MACHINE}"
    fi
  fi
fi
QEMUBOOT_CONF="${DEPLOY_DIR}/${IMAGE}-${MACHINE}.qemuboot.conf"

if [[ -f "${QEMUBOOT_CONF}" ]]; then
  target_args=("${QEMUBOOT_CONF}")
else
  target_args=("${MACHINE}" "${IMAGE}" "${FSTYPE}")
fi

# Initialize build environment so runqemu can infer paths.
# oe-init-build-env is not nounset-safe, so guard against unset vars.
{
  set +u
  : "${BBSERVER:=}"
  : "${ZSH_NAME:=}"
  source "${TOPDIR}/poky/oe-init-build-env" "${BUILD_DIR}" >/dev/null
  set -u
}

args=("$@")

network_mode_explicit=0
for a in "${args[@]}"; do
  if [[ "${a}" == "slirp" || "${a}" == bridge=* ]]; then
    network_mode_explicit=1
    break
  fi
done

if [[ "${network_mode_explicit}" -eq 0 ]]; then
  selected_net_mode=""
  case "${QEMU_NET_MODE}" in
    auto)
      if command -v ip >/dev/null 2>&1 && ip link show "${QEMU_BRIDGE_NAME}" >/dev/null 2>&1; then
        selected_net_mode="bridge=${QEMU_BRIDGE_NAME}"
      else
        selected_net_mode="slirp"
      fi
      ;;
    slirp)
      selected_net_mode="slirp"
      ;;
    bridge)
      selected_net_mode="bridge=${QEMU_BRIDGE_NAME}"
      ;;
    bridge=*)
      selected_net_mode="${QEMU_NET_MODE}"
      ;;
    *)
      echo "Unsupported QEMU_NET_MODE='${QEMU_NET_MODE}'." >&2
      echo "Use: auto | slirp | bridge | bridge=<name>" >&2
      exit 1
      ;;
  esac

  if [[ -n "${selected_net_mode}" ]]; then
    args=("${selected_net_mode}" "${args[@]}")
    echo "run-qemu.sh: using network mode '${selected_net_mode}'" >&2
  fi
fi

if [[ "${QEMU_STATIC_RES}" != "off" ]]; then
  have_qemuparams=0
  for a in "${args[@]}"; do
    if [[ "${a}" == qemuparams=* ]]; then
      have_qemuparams=1
      break
    fi
  done
  if [[ "${have_qemuparams}" -eq 0 ]]; then
    # Force a stable window size without pinning the display backend.
    args+=( "qemuparams=-global virtio-vga.xres=1280 -global virtio-vga.yres=720 -global virtio-vga.edid=on -device qemu-xhci -device usb-kbd -device usb-tablet" )
  fi
fi

exec "${RUNQEMU}" "${target_args[@]}" "${args[@]}"
