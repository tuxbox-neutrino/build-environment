#!/usr/bin/env bash
set -euo pipefail

TOPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

BUILD_DIR="${BUILD_DIR:-${TOPDIR}/build}"
MACHINE="${MACHINE:-qemux86-64}"
IMAGE="${IMAGE:-tuxbox-qemu-image}"
FSTYPE="${FSTYPE:-wic}"
RUNQEMU="${RUNQEMU:-${TOPDIR}/poky/scripts/runqemu}"

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
QEMUBOOT_CONF="${DEPLOY_DIR}/${IMAGE}-${MACHINE}.qemuboot.conf"

if [[ -f "${QEMUBOOT_CONF}" ]]; then
  target_args=("${QEMUBOOT_CONF}")
else
  target_args=("${MACHINE}" "${IMAGE}" "${FSTYPE}")
fi

# Initialize build environment so runqemu can infer paths.
source "${TOPDIR}/poky/oe-init-build-env" "${BUILD_DIR}" >/dev/null

exec "${RUNQEMU}" "${target_args[@]}" "$@"
