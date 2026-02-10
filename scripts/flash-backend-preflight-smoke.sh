#!/usr/bin/env bash
set -euo pipefail

TOPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFLIGHT_SCRIPT="${TOPDIR}/meta-tuxbox/recipes-local/flash-script/files/flash-ofgwrite-preflight.sh"
DISPATCH_SCRIPT="${TOPDIR}/meta-tuxbox/recipes-local/flash-script/files/flash-dispatch.sh"
BACKEND_SCRIPT="${TOPDIR}/meta-tuxbox/recipes-local/flash-script/files/flash-backend-script.sh"
BACKEND_OFGWRITE_SCRIPT="${TOPDIR}/meta-tuxbox/recipes-local/flash-script/files/flash-backend-ofgwrite.sh"

if [[ ! -f "${PREFLIGHT_SCRIPT}" ]]; then
  echo "ERROR: preflight script not found: ${PREFLIGHT_SCRIPT}" >&2
  exit 1
fi
if [[ ! -f "${DISPATCH_SCRIPT}" ]]; then
  echo "ERROR: dispatch script not found: ${DISPATCH_SCRIPT}" >&2
  exit 1
fi
if [[ ! -f "${BACKEND_SCRIPT}" ]]; then
  echo "ERROR: script backend handler not found: ${BACKEND_SCRIPT}" >&2
  exit 1
fi
if [[ ! -f "${BACKEND_OFGWRITE_SCRIPT}" ]]; then
  echo "ERROR: ofgwrite backend handler not found: ${BACKEND_OFGWRITE_SCRIPT}" >&2
  exit 1
fi

tmpdir="$(mktemp -d)"
cleanup() {
  rm -rf "${tmpdir}"
}
trap cleanup EXIT

fake_ofgwrite="${tmpdir}/ofgwrite"
fake_ofgwrite_log="${tmpdir}/ofgwrite-args.log"
image_dir="${tmpdir}/image"
backend_conf="${tmpdir}/flash-backend.conf"
profile_conf="${tmpdir}/flash-machine-profile.conf"
dispatch_log="${tmpdir}/dispatch.log"
preflight_log="${tmpdir}/preflight.log"
fake_preflight="${tmpdir}/flash-backend-preflight"
fake_legacy="${tmpdir}/flash-legacy"
fake_handler_script="${tmpdir}/handler-script.sh"
fake_handler_ofgwrite="${tmpdir}/handler-ofgwrite.sh"
fake_curl="${tmpdir}/curl"
fake_curl_log="${tmpdir}/curl.log"
fake_unzip="${tmpdir}/unzip"
fake_unzip_log="${tmpdir}/unzip.log"
fake_backup="${tmpdir}/backup.sh"
fake_backup_log="${tmpdir}/backup.log"
fake_cmdline="${tmpdir}/cmdline"
version_file="${tmpdir}/image-version"
image_base="${tmpdir}/image-base"
machine_name="qemux86-64"

cat >"${fake_ofgwrite}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "${FAKE_OFGWRITE_LOG:?}"
exit 0
EOF
chmod +x "${fake_ofgwrite}"

cat >"${fake_preflight}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "${FAKE_PREFLIGHT_LOG:?}"
exit 0
EOF
chmod +x "${fake_preflight}"

cat >"${fake_legacy}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'legacy:%s\n' "$*" >> "${FAKE_DISPATCH_LOG:?}"
exit 0
EOF
chmod +x "${fake_legacy}"

cat >"${fake_handler_script}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'script-handler:%s\n' "$*" >> "${FAKE_DISPATCH_LOG:?}"
exit 0
EOF
chmod +x "${fake_handler_script}"

cat >"${fake_handler_ofgwrite}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'ofgwrite-handler:%s\n' "$*" >> "${FAKE_DISPATCH_LOG:?}"
exit 0
EOF
chmod +x "${fake_handler_ofgwrite}"

cat >"${fake_curl}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
out=""
url=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|--output)
      out="$2"
      shift 2
      ;;
    -f|-s|-S|-L|-fsSL|-fL|-sSL|-fsS|-SL)
      shift
      ;;
    --*)
      shift
      ;;
    -*)
      shift
      ;;
    *)
      url="$1"
      shift
      ;;
  esac
done
printf '%s\n' "${url}" >> "${FAKE_CURL_LOG:?}"
case "${url}" in
  */imageversion)
    printf 'remote-version-1\n' > "${out:?}"
    ;;
  *.zip)
    printf 'fake-zip\n' > "${out:?}"
    ;;
  *)
    echo "unsupported url: ${url}" >&2
    exit 42
    ;;
esac
EOF
chmod +x "${fake_curl}"

cat >"${fake_unzip}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
dest=""
archive=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d)
      dest="$2"
      shift 2
      ;;
    -o|-x)
      shift
      ;;
    -*)
      shift
      ;;
    *)
      if [[ -z "${archive}" ]]; then
        archive="$1"
      fi
      shift
      ;;
  esac
done
printf '%s|%s\n' "${archive}" "${dest}" >> "${FAKE_UNZIP_LOG:?}"
mkdir -p "${dest:?}/${FAKE_MACHINE_NAME:?}"
touch "${dest}/${FAKE_MACHINE_NAME}/kernel.bin" "${dest}/${FAKE_MACHINE_NAME}/rootfs.tar.bz2"
EOF
chmod +x "${fake_unzip}"

cat >"${fake_backup}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
dest="${1:?}"
name="${2:?}"
mkdir -p "${dest}"
printf 'backup:%s|%s\n' "${dest}" "${name}" >> "${FAKE_BACKUP_LOG:?}"
printf 'dummy-backup\n' > "${dest}/${name}.tar.gz"
EOF
chmod +x "${fake_backup}"

mkdir -p "${image_dir}"
touch "${image_dir}/kernel.bin" "${image_dir}/rootfs.tar.bz2"

export FAKE_OFGWRITE_LOG="${fake_ofgwrite_log}"
export FAKE_PREFLIGHT_LOG="${preflight_log}"
export FAKE_DISPATCH_LOG="${dispatch_log}"
export FAKE_CURL_LOG="${fake_curl_log}"
export FAKE_UNZIP_LOG="${fake_unzip_log}"
export FAKE_BACKUP_LOG="${fake_backup_log}"
export FAKE_MACHINE_NAME="${machine_name}"
cat >"${backend_conf}" <<'EOF'
FLASH_BACKEND=ofgwrite
EOF
cat >"${profile_conf}" <<'EOF'
FLASH_MACHINE=qemux86-64
FLASH_MACHINE_CAP_OFGWRITE=1
EOF

echo "Running flash backend preflight smoke checks..."
sh "${PREFLIGHT_SCRIPT}" --backend script
FLASH_BACKEND_CONF_PATH="${backend_conf}" \
FLASH_MACHINE_PROFILE_PATH="${profile_conf}" \
sh "${PREFLIGHT_SCRIPT}" \
  --ofgwrite-bin "${fake_ofgwrite}" \
  --image-dir "${image_dir}"

if [[ -s "${fake_ofgwrite_log}" ]]; then
  echo "ERROR: preflight unexpectedly called ofgwrite no-write probe by default" >&2
  cat "${fake_ofgwrite_log}" >&2
  exit 1
fi

FLASH_PREFLIGHT_RUN_OFGWRITE_NOWRITE=1 \
FLASH_BACKEND_CONF_PATH="${backend_conf}" \
FLASH_MACHINE_PROFILE_PATH="${profile_conf}" \
sh "${PREFLIGHT_SCRIPT}" \
  --ofgwrite-bin "${fake_ofgwrite}" \
  --image-dir "${image_dir}"

if [[ ! -s "${fake_ofgwrite_log}" ]]; then
  echo "ERROR: no-write probe did not call ofgwrite when explicitly enabled" >&2
  exit 1
fi

if ! grep -Eq '(^|[[:space:]])-n($|[[:space:]])|--nowrite' "${fake_ofgwrite_log}"; then
  echo "ERROR: preflight call did not use no-write mode" >&2
  cat "${fake_ofgwrite_log}" >&2
  exit 1
fi

cat >"${profile_conf}" <<'EOF'
FLASH_MACHINE=qemux86-64
FLASH_MACHINE_CAP_OFGWRITE=0
EOF

if FLASH_BACKEND_CONF_PATH="${backend_conf}" \
   FLASH_MACHINE_PROFILE_PATH="${profile_conf}" \
   sh "${PREFLIGHT_SCRIPT}" --ofgwrite-bin "${fake_ofgwrite}" --image-dir "${image_dir}"; then
  echo "ERROR: expected preflight failure for unsupported machine profile" >&2
  exit 1
fi

cat >"${backend_conf}" <<'EOF'
FLASH_BACKEND=script
EOF
FLASH_BACKEND_CONF_PATH="${backend_conf}" \
FLASH_BACKEND_SCRIPT_HANDLER="${fake_handler_script}" \
FLASH_BACKEND_OFGWRITE_HANDLER="${fake_handler_ofgwrite}" \
sh "${DISPATCH_SCRIPT}" 2 /tmp/demo-image

if ! grep -q '^script-handler:' "${dispatch_log}"; then
  echo "ERROR: dispatcher did not route script backend correctly" >&2
  cat "${dispatch_log}" >&2
  exit 1
fi

cat >"${backend_conf}" <<'EOF'
FLASH_BACKEND=ofgwrite
EOF
FLASH_BACKEND_CONF_PATH="${backend_conf}" \
FLASH_BACKEND_SCRIPT_HANDLER="${fake_handler_script}" \
FLASH_BACKEND_OFGWRITE_HANDLER="${fake_handler_ofgwrite}" \
sh "${DISPATCH_SCRIPT}" 2 /tmp/demo-image

if ! grep -q '^ofgwrite-handler:' "${dispatch_log}"; then
  echo "ERROR: dispatcher did not route ofgwrite backend correctly" >&2
  cat "${dispatch_log}" >&2
  exit 1
fi

: > "${fake_ofgwrite_log}"
: > "${preflight_log}"
printf 'console=ttyS0 root=/dev/vda rootsubdir=linuxrootfs4 rw\n' > "${fake_cmdline}"
FAKE_OFGWRITE_LOG="${fake_ofgwrite_log}" \
FAKE_PREFLIGHT_LOG="${preflight_log}" \
FLASH_BACKEND_PREFLIGHT_BIN="${fake_preflight}" \
FLASH_BACKEND_OFGWRITE_BIN="${fake_ofgwrite}" \
FLASH_PROC_CMDLINE_FILE="${fake_cmdline}" \
sh "${BACKEND_OFGWRITE_SCRIPT}" 2 "${image_dir}"

if ! grep -q -- '--backend ofgwrite' "${preflight_log}"; then
  echo "ERROR: ofgwrite backend did not invoke preflight with backend marker" >&2
  cat "${preflight_log}" >&2
  exit 1
fi
if ! grep -Eq '(^|[[:space:]])-m([[:space:]]|$)2' "${fake_ofgwrite_log}"; then
  echo "ERROR: ofgwrite backend did not invoke slot mapping correctly" >&2
  cat "${fake_ofgwrite_log}" >&2
  exit 1
fi

printf 'console=ttyS0 root=/dev/vda rootsubdir=linuxrootfs2 rw\n' > "${fake_cmdline}"
if FAKE_OFGWRITE_LOG="${fake_ofgwrite_log}" \
   FAKE_PREFLIGHT_LOG="${preflight_log}" \
   FLASH_BACKEND_PREFLIGHT_BIN="${fake_preflight}" \
   FLASH_BACKEND_OFGWRITE_BIN="${fake_ofgwrite}" \
   FLASH_PROC_CMDLINE_FILE="${fake_cmdline}" \
   sh "${BACKEND_OFGWRITE_SCRIPT}" 2 "${image_dir}"; then
  echo "ERROR: expected active-slot protection to block slot 2" >&2
  exit 1
fi

: > "${fake_ofgwrite_log}"
: > "${preflight_log}"
: > "${fake_backup_log}"
FAKE_OFGWRITE_LOG="${fake_ofgwrite_log}" \
FAKE_PREFLIGHT_LOG="${preflight_log}" \
FAKE_BACKUP_LOG="${fake_backup_log}" \
FLASH_BACKEND_PREFLIGHT_BIN="${fake_preflight}" \
FLASH_BACKEND_OFGWRITE_BIN="${fake_ofgwrite}" \
FLASH_PROC_CMDLINE_FILE="${fake_cmdline}" \
FLASH_OFGWRITE_ALLOW_ACTIVE_SLOT_DEFAULT=1 \
FLASH_OFGWRITE_ACTIVE_SLOT_REQUIRE_BACKUP_DEFAULT=1 \
FLASH_OFGWRITE_ACTIVE_SLOT_BACKUP_DIR_DEFAULT="${tmpdir}/backups" \
FLASH_BACKUP_BIN="${fake_backup}" \
sh "${BACKEND_OFGWRITE_SCRIPT}" 2 "${image_dir}"

if [[ ! -s "${fake_backup_log}" ]]; then
  echo "ERROR: active-slot allow path did not run backup hook" >&2
  exit 1
fi

cat >"${version_file}" <<'EOF'
machine=qemux86-64
imagename=tuxbox-qemu-image
image_update_url=https://example.invalid/images
image_update_info_file=imageversion
image_file_name=tuxbox-qemu-image_qemux86-64_ofgwrite.zip
EOF

mkdir -p "${image_base}/backup/partition_2/${machine_name}"
touch "${image_base}/backup/partition_2/${machine_name}/kernel.bin"
touch "${image_base}/backup/partition_2/${machine_name}/rootfs.tar.bz2"

: > "${fake_ofgwrite_log}"
: > "${preflight_log}"
printf 'console=ttyS0 root=/dev/vda rootsubdir=linuxrootfs4 rw\n' > "${fake_cmdline}"
FLASH_VERSION_FILE_PATH="${version_file}" \
FLASH_IMAGE_BASE_OVERRIDE="${image_base}" \
FAKE_OFGWRITE_LOG="${fake_ofgwrite_log}" \
FAKE_PREFLIGHT_LOG="${preflight_log}" \
FLASH_BACKEND_PREFLIGHT_BIN="${fake_preflight}" \
FLASH_BACKEND_OFGWRITE_BIN="${fake_ofgwrite}" \
FLASH_PROC_CMDLINE_FILE="${fake_cmdline}" \
sh "${BACKEND_OFGWRITE_SCRIPT}" 2 restore

if ! grep -Eq '(^|[[:space:]])-m([[:space:]]|$)2' "${fake_ofgwrite_log}"; then
  echo "ERROR: restore mode did not call ofgwrite with slot 2" >&2
  cat "${fake_ofgwrite_log}" >&2
  exit 1
fi
if ! grep -q -- "--image-dir ${image_base}/backup/partition_2/${machine_name}" "${preflight_log}"; then
  echo "ERROR: restore mode did not resolve expected image directory" >&2
  cat "${preflight_log}" >&2
  exit 1
fi

rm -rf "${image_base}"
mkdir -p "${image_base}"
: > "${fake_ofgwrite_log}"
: > "${preflight_log}"
: > "${fake_curl_log}"
: > "${fake_unzip_log}"
FLASH_VERSION_FILE_PATH="${version_file}" \
FLASH_IMAGE_BASE_OVERRIDE="${image_base}" \
FLASH_CURL_BIN="${fake_curl}" \
FLASH_UNZIP_BIN="${fake_unzip}" \
FAKE_OFGWRITE_LOG="${fake_ofgwrite_log}" \
FAKE_PREFLIGHT_LOG="${preflight_log}" \
FLASH_BACKEND_PREFLIGHT_BIN="${fake_preflight}" \
FLASH_BACKEND_OFGWRITE_BIN="${fake_ofgwrite}" \
FLASH_PROC_CMDLINE_FILE="${fake_cmdline}" \
sh "${BACKEND_OFGWRITE_SCRIPT}" 2 force

if ! grep -q 'https://example.invalid/images/imageversion' "${fake_curl_log}"; then
  echo "ERROR: force download mode did not query online imageversion" >&2
  cat "${fake_curl_log}" >&2
  exit 1
fi
if ! grep -q 'https://example.invalid/images/tuxbox-qemu-image_qemux86-64_ofgwrite.zip' "${fake_curl_log}"; then
  echo "ERROR: force download mode did not fetch image zip" >&2
  cat "${fake_curl_log}" >&2
  exit 1
fi
if ! [[ -s "${fake_unzip_log}" ]]; then
  echo "ERROR: force download mode did not run unzip" >&2
  exit 1
fi
if ! grep -q -- "--image-dir ${image_base}/${machine_name}" "${preflight_log}"; then
  echo "ERROR: force download mode did not use unpacked machine directory" >&2
  cat "${preflight_log}" >&2
  exit 1
fi

FLASH_LEGACY_BIN="${fake_legacy}" sh "${BACKEND_SCRIPT}" 1 /tmp/legacy-image
if ! grep -q '^legacy:' "${dispatch_log}"; then
  echo "ERROR: script backend handler did not invoke legacy binary" >&2
  cat "${dispatch_log}" >&2
  exit 1
fi

cat > "${profile_conf}" <<'EOF'
FLASH_SCRIPT_MODE=legacy
EOF
FLASH_LEGACY_BIN="${fake_legacy}" \
FLASH_MACHINE_PROFILE_PATH="${profile_conf}" \
sh "${BACKEND_SCRIPT}" 3 /tmp/legacy-image-profile

cat > "${profile_conf}" <<'EOF'
FLASH_SCRIPT_MODE=invalid-mode
EOF
if FLASH_LEGACY_BIN="${fake_legacy}" \
   FLASH_MACHINE_PROFILE_PATH="${profile_conf}" \
   sh "${BACKEND_SCRIPT}" 3 /tmp/legacy-image-profile; then
  echo "ERROR: script backend handler accepted invalid FLASH_SCRIPT_MODE" >&2
  exit 1
fi

echo "Flash backend preflight/dispatch smoke checks passed."
