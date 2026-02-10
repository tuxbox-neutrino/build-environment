#!/usr/bin/env bash
set -euo pipefail

TOPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFLIGHT_SCRIPT="${TOPDIR}/meta-tuxbox/recipes-local/flash-script/files/flash-ofgwrite-preflight.sh"

if [[ ! -f "${PREFLIGHT_SCRIPT}" ]]; then
  echo "ERROR: preflight script not found: ${PREFLIGHT_SCRIPT}" >&2
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

cat >"${fake_ofgwrite}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "${FAKE_OFGWRITE_LOG:?}"
case " $* " in
  *" -n "*|*" --nowrite "*)
    ;;
  *)
    echo "missing --nowrite/-n option" >&2
    exit 31
    ;;
esac
exit 0
EOF
chmod +x "${fake_ofgwrite}"

mkdir -p "${image_dir}"
touch "${image_dir}/kernel.bin" "${image_dir}/rootfs.tar.bz2"

export FAKE_OFGWRITE_LOG="${fake_ofgwrite_log}"

echo "Running flash backend preflight smoke checks..."
sh "${PREFLIGHT_SCRIPT}" --backend script
sh "${PREFLIGHT_SCRIPT}" \
  --backend ofgwrite \
  --ofgwrite-bin "${fake_ofgwrite}" \
  --image-dir "${image_dir}"

if [[ ! -s "${fake_ofgwrite_log}" ]]; then
  echo "ERROR: fake ofgwrite did not capture any invocation" >&2
  exit 1
fi

if ! grep -Eq '(^|[[:space:]])-n($|[[:space:]])|--nowrite' "${fake_ofgwrite_log}"; then
  echo "ERROR: preflight call did not use no-write mode" >&2
  cat "${fake_ofgwrite_log}" >&2
  exit 1
fi

echo "Flash backend preflight smoke checks passed."
