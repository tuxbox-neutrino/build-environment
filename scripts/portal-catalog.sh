#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TOPDIR=$(cd "${SCRIPT_DIR}/.." && pwd)

MACHINE=${MACHINE:-hd51}
DISTRO_TYPE=${DISTRO_TYPE:-release}
SOURCE_DIR=${SOURCE_DIR:-}
FEED_ROOT=${FEED_ROOT:-"${TOPDIR}/portal-feed"}
CATALOG_OUT=${CATALOG_OUT:-"${FEED_ROOT}/catalog.json"}
ARTIFACT_BASE_URL=${ARTIFACT_BASE_URL:-"https://images.tuxbox-neutrino.org/feed"}
ONLINE_UPDATE_REPO=${ONLINE_UPDATE_REPO:-"${TOPDIR}/../online-update"}
ALLOWED_CHANNELS=${ALLOWED_CHANNELS:-"release,beta,nightly"}

if [[ ! -d "${ONLINE_UPDATE_REPO}" ]]; then
    echo "online-update repo not found: ${ONLINE_UPDATE_REPO}" >&2
    exit 1
fi

if [[ ! -x "${ONLINE_UPDATE_REPO}/tools/build-catalog.php" ]]; then
    echo "missing catalog builder: ${ONLINE_UPDATE_REPO}/tools/build-catalog.php" >&2
    exit 1
fi

if [[ -z "${SOURCE_DIR}" ]]; then
    candidates=(
        "${TOPDIR}/build/build/tmp-${MACHINE}/deploy/images/${MACHINE}"
        "${TOPDIR}/build/tmp-${MACHINE}/deploy/images/${MACHINE}"
        "${TOPDIR}/builds/tmp-${MACHINE}/deploy/images/${MACHINE}"
    )
    for candidate in "${candidates[@]}"; do
        if [[ -d "${candidate}" ]]; then
            SOURCE_DIR="${candidate}"
            break
        fi
    done
fi

if [[ -z "${SOURCE_DIR}" ]]; then
    SOURCE_DIR=$(find "${TOPDIR}" -maxdepth 6 -type d -path "*/tmp-${MACHINE}/deploy/images/${MACHINE}" | head -n 1 || true)
fi

if [[ -z "${SOURCE_DIR}" || ! -d "${SOURCE_DIR}" ]]; then
    echo "cannot locate deploy source directory for machine ${MACHINE}" >&2
    exit 1
fi

manifest_src="${SOURCE_DIR}/manifest.json"
if [[ ! -f "${manifest_src}" ]]; then
    echo "missing ${manifest_src}" >&2
    echo "rebuild image with updated tuxbox-version.bbclass to generate manifest metadata" >&2
    exit 1
fi

manifest_channel=$(jq -r '.channel // empty' "${manifest_src}")
manifest_imagedir=$(jq -r '.imagedir // empty' "${manifest_src}")
manifest_build_date=$(jq -r '.build_date // empty' "${manifest_src}")
manifest_image_name=$(jq -r '.image_name // empty' "${manifest_src}")

if [[ -z "${manifest_channel}" || -z "${manifest_imagedir}" || -z "${manifest_build_date}" ]]; then
    echo "manifest is missing required fields (channel/imagedir/build_date): ${manifest_src}" >&2
    exit 1
fi

stage_dir="${FEED_ROOT}/${manifest_channel}/${manifest_imagedir}/${manifest_build_date}"
mkdir -p "${stage_dir}"

cp -f "${manifest_src}" "${stage_dir}/manifest.json"

marker_src="${SOURCE_DIR}/imageversion"
if [[ -f "${marker_src}" ]]; then
    cp -f "${marker_src}" "${stage_dir}/imageversion"
else
    printf '%s\n' "${manifest_image_name}" > "${stage_dir}/imageversion"
fi

mapfile -t manifest_files < <(jq -r '.files[]?.name // empty' "${manifest_src}")
if [[ ${#manifest_files[@]} -eq 0 ]]; then
    echo "manifest has no files[] entries: ${manifest_src}" >&2
    exit 1
fi

for name in "${manifest_files[@]}"; do
    if [[ ! "${name}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{1,255}$ ]]; then
        echo "invalid file entry in manifest: ${name}" >&2
        exit 1
    fi

    src="${SOURCE_DIR}/${name}"
    if [[ ! -f "${src}" ]]; then
        echo "manifest file missing in deploy dir: ${src}" >&2
        exit 1
    fi

    cp -f "${src}" "${stage_dir}/${name}"

    sidecar_src="${src}.sha256"
    sidecar_dst="${stage_dir}/${name}.sha256"
    if [[ -f "${sidecar_src}" ]]; then
        cp -f "${sidecar_src}" "${sidecar_dst}"
    else
        sha256sum "${stage_dir}/${name}" | awk -v fn="${name}" '{print $1 "  " fn}' > "${sidecar_dst}"
    fi

    sidecar_md5_src="${src}.md5"
    sidecar_md5_dst="${stage_dir}/${name}.md5"
    if [[ -f "${sidecar_md5_src}" ]]; then
        cp -f "${sidecar_md5_src}" "${sidecar_md5_dst}"
    else
        md5sum "${stage_dir}/${name}" | awk -v fn="${name}" '{print $1 "  " fn}' > "${sidecar_md5_dst}"
    fi
done

if [[ -f "${SOURCE_DIR}/manifest.json.sha256" ]]; then
    cp -f "${SOURCE_DIR}/manifest.json.sha256" "${stage_dir}/manifest.json.sha256"
else
    sha256sum "${stage_dir}/manifest.json" | awk '{print $1 "  manifest.json"}' > "${stage_dir}/manifest.json.sha256"
fi

if [[ -f "${SOURCE_DIR}/changelog.txt" ]]; then
    cp -f "${SOURCE_DIR}/changelog.txt" "${stage_dir}/changelog.txt"
fi

tmp_catalog="${CATALOG_OUT}.tmp.$$"
cleanup_tmp_catalog() {
    rm -f "${tmp_catalog}"
}
trap cleanup_tmp_catalog EXIT INT TERM

php "${ONLINE_UPDATE_REPO}/tools/build-catalog.php" \
    --feed-root "${FEED_ROOT}" \
    --artifact-base-url "${ARTIFACT_BASE_URL}" \
    --allowed-channels "${ALLOWED_CHANNELS}" \
    --out "${tmp_catalog}"

mv -f "${tmp_catalog}" "${CATALOG_OUT}"
trap - EXIT INT TERM

echo "feed stage: ${stage_dir}"
echo "catalog: ${CATALOG_OUT}"
