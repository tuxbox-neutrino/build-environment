#!/usr/bin/env bash
set -euo pipefail

TOPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FEED_DIR="${FEED_SERVER_DIR:-${TOPDIR}/feed-server}"
WWW_DIR="${FEED_SERVER_WWW:-${FEED_DIR}/www}"
RUN_DIR="${FEED_SERVER_RUN:-${FEED_DIR}/run}"
LOG_DIR="${FEED_SERVER_LOGS:-${FEED_DIR}/logs}"
PID_FILE="${RUN_DIR}/feed-server.pid"
META_FILE="${RUN_DIR}/feed-server.env"
LIGHTTPD_CONF="${RUN_DIR}/lighttpd.conf"

usage() {
    cat <<'EOF'
Usage: scripts/feed-server.sh <command> [options]

Commands:
  publish   Link feed-server/www/<machine>/ipk to the build deploy/ipk dir
  publish-all
            Link every discovered deploy/ipk dir below the build root
  start     Start the static feed server
  stop      Stop the static feed server
  restart   Restart the static feed server
  status    Show static feed server status
  url       Print the feed URL for a machine
  urls      Print feed URLs for all currently published machines

Options:
  --machine <name>      Target MACHINE
  --builddir <path>     Build directory to inspect for deploy/ipk
  --deploy-ipk <path>   Explicit deploy/ipk directory
  --port <port>         HTTP port (default: LOCAL_FEED_PORT or 33333)
  --host <host|auto>    URL host (default: LOCAL_FEED_HOST or auto)
  --bind <addr>         Bind address (default: LOCAL_FEED_BIND or 0.0.0.0)
  --backend <name>      auto|lighttpd|python (default: LOCAL_FEED_BACKEND or auto)
  --base-url <url>      Explicit full feed URL
EOF
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

warn() {
    echo "WARNING: $*" >&2
}

is_running() {
    [[ -f "${PID_FILE}" ]] || return 1
    local pid
    pid="$(tr -d '[:space:]' < "${PID_FILE}")"
    [[ -n "${pid}" ]] || return 1
    kill -0 "${pid}" 2>/dev/null
}

is_valid_machine() {
    local machine="$1"
    [[ -n "${machine}" && "${machine}" =~ ^[A-Za-z0-9_.+-]+$ ]]
}

validate_machine() {
    local machine="$1"
    [[ -n "${machine}" ]] || die "--machine is required"
    is_valid_machine "${machine}" || die "invalid machine name: ${machine}"
}

primary_ipv4() {
    local host
    host="$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9.]\+\).*/\1/p' | head -n 1 || true)"
    if [[ -z "${host}" ]]; then
        host="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
    fi
    if [[ -z "${host}" ]]; then
        host="127.0.0.1"
    fi
    printf '%s\n' "${host}"
}

feed_url() {
    local machine="$1"
    local port="$2"
    local host="$3"
    local base_url="$4"

    if [[ -n "${base_url}" ]]; then
        base_url="${base_url//\$\{MACHINE\}/${machine}}"
        base_url="${base_url//\{machine\}/${machine}}"
        printf '%s\n' "${base_url%/}"
        return
    fi

    if [[ -z "${host}" || "${host}" == "auto" ]]; then
        host="$(primary_ipv4)"
    fi
    printf 'http://%s:%s/%s/ipk\n' "${host}" "${port}" "${machine}"
}

find_deploy_ipk() {
    local builddir="$1"
    local machine="$2"
    local explicit="$3"

    if [[ -n "${explicit}" ]]; then
        [[ -d "${explicit}" ]] || die "deploy/ipk does not exist: ${explicit}"
        readlink -f "${explicit}"
        return
    fi

    local candidates=(
        "${builddir}/tmp/deploy/ipk"
        "${builddir}/build/tmp/deploy/ipk"
        "${builddir}/build/tmp-${machine}/deploy/ipk"
        "${builddir}/tmp-${machine}/deploy/ipk"
    )

    local path
    for path in "${candidates[@]}"; do
        if [[ -d "${path}" ]]; then
            readlink -f "${path}"
            return
        fi
    done

    path="$(find "${builddir}" -maxdepth 6 -type d -path '*/deploy/ipk' 2>/dev/null | sort | head -n 1 || true)"
    if [[ -n "${path}" ]]; then
        readlink -f "${path}"
        return
    fi

    die "could not find deploy/ipk below ${builddir}"
}

machine_from_deploy_ipk() {
    local deploy_ipk="$1"
    local parent
    local name

    parent="${deploy_ipk%/deploy/ipk}"
    name="${parent##*/}"
    if [[ "${name}" == tmp-* ]]; then
        printf '%s\n' "${name#tmp-}"
        return 0
    fi

    parent="${parent%/tmp}"
    name="${parent##*/}"
    if [[ "${name}" == build-* ]]; then
        printf '%s\n' "${name#build-}"
        return 0
    fi

    return 1
}

deploy_has_content() {
    local deploy_ipk="$1"
    [[ -n "$(find "${deploy_ipk}" -mindepth 1 -print -quit 2>/dev/null)" ]]
}

publish_deploy_ipk() {
    local machine="$1"
    local deploy_ipk="$2"
    validate_machine "${machine}"
    [[ -d "${deploy_ipk}" ]] || die "deploy/ipk does not exist: ${deploy_ipk}"

    mkdir -p "${WWW_DIR}/${machine}"
    rm -rf "${WWW_DIR:?}/${machine}/ipk"
    ln -s "$(readlink -f "${deploy_ipk}")" "${WWW_DIR}/${machine}/ipk"
    echo "published: ${machine} -> ${WWW_DIR}/${machine}/ipk"
}

discover_deploy_ipks() {
    local root="$1"
    shopt -s nullglob
    local candidates=(
        "${root}"/build/tmp-*/deploy/ipk
        "${root}"/build/build/tmp-*/deploy/ipk
        "${root}"/builds/build/tmp-*/deploy/ipk
        "${root}"/tmp-*/deploy/ipk
        "${root}"/build-*/tmp/deploy/ipk
    )
    shopt -u nullglob

    local path
    for path in "${candidates[@]}"; do
        [[ -d "${path}" ]] || continue
        readlink -f "${path}"
    done | sort -u
}

write_lighttpd_conf() {
    local port="$1"
    local bind_addr="$2"
    mkdir -p "${RUN_DIR}" "${LOG_DIR}" "${WWW_DIR}"
    cat > "${LIGHTTPD_CONF}" <<EOF
server.document-root = "${WWW_DIR}"
server.port = ${port}
server.bind = "${bind_addr}"
server.pid-file = "${PID_FILE}"
server.errorlog = "${LOG_DIR}/lighttpd.error.log"
dir-listing.activate = "enable"
mimetype.assign = (
  ".gz" => "application/gzip",
  ".ipk" => "application/octet-stream",
  "" => "application/octet-stream"
)
EOF
}

do_publish() {
    local machine="$1"
    local builddir="$2"
    local deploy_ipk="$3"
    validate_machine "${machine}"
    [[ -d "${builddir}" ]] || die "--builddir does not exist: ${builddir}"

    deploy_ipk="$(find_deploy_ipk "${builddir}" "${machine}" "${deploy_ipk}")"
    publish_deploy_ipk "${machine}" "${deploy_ipk}"
}

do_urls() {
    local port="$1"
    local host="$2"
    local base_url="$3"
    local machine_dir
    local machine
    local found=0

    shopt -s nullglob
    for machine_dir in "${WWW_DIR}"/*; do
        [[ -d "${machine_dir}" ]] || continue
        [[ -e "${machine_dir}/ipk" || -L "${machine_dir}/ipk" ]] || continue
        machine="${machine_dir##*/}"
        if ! is_valid_machine "${machine}"; then
            warn "skip invalid published machine directory: ${machine_dir}"
            continue
        fi
        feed_url "${machine}" "${port}" "${host}" "${base_url}"
        found=1
    done
    shopt -u nullglob

    if [[ "${found}" -eq 0 ]]; then
        warn "no published feeds found below ${WWW_DIR}"
        return 1
    fi
}

do_publish_all() {
    local builddir="$1"
    local port="$2"
    local host="$3"
    local base_url="$4"
    [[ -d "${builddir}" ]] || die "--builddir does not exist: ${builddir}"

    local count=0
    local deploy_ipk
    local machine
    declare -A seen=()

    while IFS= read -r deploy_ipk; do
        [[ -n "${deploy_ipk}" ]] || continue
        if ! machine="$(machine_from_deploy_ipk "${deploy_ipk}")"; then
            warn "skip unsupported deploy layout: ${deploy_ipk}"
            continue
        fi
        if ! is_valid_machine "${machine}"; then
            warn "skip invalid machine from ${deploy_ipk}"
            continue
        fi
        if [[ -n "${seen[${machine}]:-}" ]]; then
            warn "skip duplicate machine ${machine}: ${deploy_ipk}"
            continue
        fi
        if ! deploy_has_content "${deploy_ipk}"; then
            warn "skip empty deploy/ipk for ${machine}: ${deploy_ipk}"
            continue
        fi

        publish_deploy_ipk "${machine}" "${deploy_ipk}"
        seen["${machine}"]=1
        count=$((count + 1))
    done < <(discover_deploy_ipks "${builddir}")

    if [[ "${count}" -eq 0 ]]; then
        die "no deploy/ipk directories found below ${builddir}"
    fi

    echo
    do_urls "${port}" "${host}" "${base_url}"
}

select_backend() {
    local backend="$1"
    if [[ "${backend}" == "auto" ]]; then
        if command -v lighttpd >/dev/null 2>&1; then
            backend="lighttpd"
        else
            backend="python"
        fi
    fi
    case "${backend}" in
        lighttpd)
            command -v lighttpd >/dev/null 2>&1 || die "lighttpd not found; use --backend python"
            ;;
        python)
            command -v python3 >/dev/null 2>&1 || die "python3 not found"
            ;;
        *)
            die "unsupported backend: ${backend}"
            ;;
    esac
    printf '%s\n' "${backend}"
}

do_start() {
    local machine="$1"
    local port="$2"
    local host="$3"
    local bind_addr="$4"
    local backend="$5"
    local base_url="$6"

    mkdir -p "${RUN_DIR}" "${LOG_DIR}" "${WWW_DIR}"
    if is_running; then
        echo "feed server already running (pid $(cat "${PID_FILE}"))"
        [[ -n "${machine}" ]] && echo "url: $(feed_url "${machine}" "${port}" "${host}" "${base_url}")"
        return 0
    fi

    backend="$(select_backend "${backend}")"
    case "${backend}" in
        lighttpd)
            write_lighttpd_conf "${port}" "${bind_addr}"
            nohup lighttpd -D -f "${LIGHTTPD_CONF}" > "${LOG_DIR}/lighttpd.stdout.log" 2>&1 &
            ;;
        python)
            (
                cd "${WWW_DIR}"
                exec python3 -m http.server "${port}" --bind "${bind_addr}"
            ) > "${LOG_DIR}/python-http.server.log" 2>&1 &
            ;;
    esac

    local pid="$!"
    printf '%s\n' "${pid}" > "${PID_FILE}"
    {
        printf 'backend=%s\n' "${backend}"
        printf 'port=%s\n' "${port}"
        printf 'bind=%s\n' "${bind_addr}"
        printf 'www=%s\n' "${WWW_DIR}"
    } > "${META_FILE}"
    sleep 0.3
    if ! kill -0 "${pid}" 2>/dev/null; then
        rm -f "${PID_FILE}"
        die "feed server failed to start; see ${LOG_DIR}"
    fi

    echo "feed server started (backend=${backend}, pid=${pid})"
    [[ -n "${machine}" ]] && echo "url: $(feed_url "${machine}" "${port}" "${host}" "${base_url}")"
    return 0
}

do_stop() {
    if ! is_running; then
        rm -f "${PID_FILE}"
        echo "feed server stopped"
        return
    fi
    local pid
    pid="$(cat "${PID_FILE}")"
    kill "${pid}" 2>/dev/null || true
    local i
    for i in 1 2 3 4 5; do
        if ! kill -0 "${pid}" 2>/dev/null; then
            break
        fi
        sleep 0.2
    done
    if kill -0 "${pid}" 2>/dev/null; then
        kill -9 "${pid}" 2>/dev/null || true
    fi
    rm -f "${PID_FILE}"
    echo "feed server stopped"
}

do_status() {
    if is_running; then
        echo "feed server running (pid $(cat "${PID_FILE}"))"
        [[ -f "${META_FILE}" ]] && sed 's/^/  /' "${META_FILE}"
    else
        echo "feed server stopped"
    fi
}

cmd="${1:-}"
if [[ -z "${cmd}" ]]; then
    usage
    exit 1
fi
shift

machine="${MACHINE:-}"
builddir="${BUILDDIR:-${TOPDIR}/builds}"
deploy_ipk=""
port="${LOCAL_FEED_PORT:-33333}"
host="${LOCAL_FEED_HOST:-auto}"
bind_addr="${LOCAL_FEED_BIND:-0.0.0.0}"
backend="${LOCAL_FEED_BACKEND:-auto}"
base_url="${LOCAL_FEED_BASE_URL:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --machine) machine="${2:-}"; shift 2 ;;
        --builddir) builddir="${2:-}"; shift 2 ;;
        --deploy-ipk) deploy_ipk="${2:-}"; shift 2 ;;
        --port) port="${2:-}"; shift 2 ;;
        --host) host="${2:-}"; shift 2 ;;
        --bind) bind_addr="${2:-}"; shift 2 ;;
        --backend) backend="${2:-}"; shift 2 ;;
        --base-url) base_url="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
done

case "${cmd}" in
    publish)
        do_publish "${machine}" "${builddir}" "${deploy_ipk}"
        ;;
    publish-all)
        do_publish_all "${builddir}" "${port}" "${host}" "${base_url}"
        ;;
    start)
        do_start "${machine}" "${port}" "${host}" "${bind_addr}" "${backend}" "${base_url}"
        ;;
    stop)
        do_stop
        ;;
    restart)
        do_stop
        do_start "${machine}" "${port}" "${host}" "${bind_addr}" "${backend}" "${base_url}"
        ;;
    status)
        do_status
        ;;
    url)
        validate_machine "${machine}"
        feed_url "${machine}" "${port}" "${host}" "${base_url}"
        ;;
    urls)
        do_urls "${port}" "${host}" "${base_url}"
        ;;
    *)
        usage
        exit 1
        ;;
esac
