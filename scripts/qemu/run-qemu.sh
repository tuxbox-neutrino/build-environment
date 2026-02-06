#!/usr/bin/env bash
set -euo pipefail

TOPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

BUILD_DIR="${BUILD_DIR:-${TOPDIR}/build}"
MACHINE="${MACHINE:-qemux86-64}"
IMAGE="${IMAGE:-tuxbox-qemu-image}"
FSTYPE="${FSTYPE:-wic}"
RUNQEMU="${RUNQEMU:-${TOPDIR}/poky/scripts/runqemu}"
QEMU_STATIC_RES="${QEMU_STATIC_RES:-1280x720}"

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
