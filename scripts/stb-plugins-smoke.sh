#!/usr/bin/env bash
set -euo pipefail

TOPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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
DISTRO="${DISTRO:-tuxbox}"
DISTRO_TYPE="${DISTRO_TYPE:-release}"
FORCE_TASKS="${FORCE_TASKS:-1}"
TASKS="${TASKS:-unpack install}"
STB_PLUGIN_RECIPES="${STB_PLUGIN_RECIPES:-stb-backup stb-flash stb-flash-local stb-log stb-move stb-plugins stb-restore stb-shell stb-startup}"

OE_INIT="${TOPDIR}/poky/oe-init-build-env"
CLI="${TOPDIR}/cli.py"

if [[ ! -f "${OE_INIT}" ]]; then
  echo "ERROR: OE init script not found: ${OE_INIT}" >&2
  exit 1
fi

if [[ ! -x "${CLI}" ]]; then
  echo "ERROR: cli.py not executable or missing: ${CLI}" >&2
  exit 1
fi

if [[ ! -f "${BUILD_DIR}/conf/local.conf" || ! -f "${BUILD_DIR}/conf/bblayers.conf" ]]; then
  echo "Build config missing in ${BUILD_DIR}, generating it..."
  "${CLI}" config --machine "${MACHINE}" --distro "${DISTRO}" --distro-type "${DISTRO_TYPE}"
fi

read -r -a task_list <<< "${TASKS}"
read -r -a recipe_list <<< "${STB_PLUGIN_RECIPES}"

if [[ "${#task_list[@]}" -eq 0 || "${#recipe_list[@]}" -eq 0 ]]; then
  echo "ERROR: task list or recipe list is empty" >&2
  exit 1
fi

force_args=()
if [[ "${FORCE_TASKS}" == "1" || "${FORCE_TASKS}" == "yes" || "${FORCE_TASKS}" == "true" ]]; then
  force_args=(-f)
fi

echo "STB plugin smoke check"
echo "  BUILD_DIR=${BUILD_DIR}"
echo "  MACHINE=${MACHINE}"
echo "  TASKS=${TASKS}"
echo "  RECIPES=${STB_PLUGIN_RECIPES}"

(
  set +u
  source "${OE_INIT}" "${BUILD_DIR}" >/dev/null
  set -u
  for task in "${task_list[@]}"; do
    echo "Running: bitbake ${force_args[*]} -c ${task} ${recipe_list[*]}"
    bitbake "${force_args[@]}" -c "${task}" "${recipe_list[@]}"
  done
)

echo "STB plugin smoke check completed successfully."
