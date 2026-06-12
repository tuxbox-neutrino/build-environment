#!/usr/bin/env bash
set -euo pipefail

TOPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_SERVER_DIR="${IMAGE_SERVER_DIR:-${TOPDIR}/image-server}"
RUN_DIR="${IMAGE_SERVER_RUN:-${IMAGE_SERVER_DIR}/run}"
LOG_DIR="${IMAGE_SERVER_LOGS:-${IMAGE_SERVER_DIR}/logs}"
PID_FILE="${RUN_DIR}/image-server.pid"
META_FILE="${RUN_DIR}/image-server.env"
PHP_LOG="${LOG_DIR}/php-server.log"
AUTH_LOG="${LOG_DIR}/auth.log"
CLI="${CLI:-${TOPDIR}/cli.py}"

usage() {
	cat <<'EOF'
Usage: scripts/image-server.sh <command> [options]

Commands:
  start     Start the local PHP image server from the online-update repo
  stop      Stop the local image server
  status    Show local image server status
  url       Print Neutrino image_update_url and test curl command
  base-url  Print the image server base URL

Options:
  --machine <name>              Target MACHINE
  --machinebuild <name>         Optional MACHINEBUILD
  --builddir <path>             Build directory to inspect
  --feed-root <path>            Local staged portal feed root
  --catalog <path>              Local catalog.json
  --online-update-repo <path>   online-update repository
  --channel <name>              Feed channel override
  --imagedir <name>             Online image directory override
  --port <port>                 HTTP port (default: IMAGE_SERVER_PORT or 33334)
  --host <host|auto>            URL host (default: IMAGE_SERVER_HOST or auto)
  --bind <addr>                 Bind address (default: IMAGE_SERVER_BIND or 0.0.0.0)
  --base-url <url>              Explicit image server base URL
  --admin-webif-url <url>       Explicit admin WebIF URL
EOF
}

die() {
	echo "ERROR: $*" >&2
	exit 1
}

warn() {
	echo "WARNING: $*" >&2
}

pid_is_image_server() {
	local pid="$1"
	[[ -n "${pid}" ]] || return 1
	kill -0 "${pid}" 2>/dev/null || return 1
	local cmdline=""
	if [[ -r "/proc/${pid}/cmdline" ]]; then
		cmdline="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
	fi
	[[ "${cmdline}" == *php* && "${cmdline}" == *dev-server-router.php* ]]
}

is_running() {
	[[ -f "${PID_FILE}" ]] || return 1
	local pid
	pid="$(tr -d '[:space:]' < "${PID_FILE}")"
	[[ -n "${pid}" ]] || return 1
	pid_is_image_server "${pid}"
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

trim_trailing_slash() {
	local value="$1"
	while [[ "${value}" == */ && "${value}" != "/" ]]; do
		value="${value%/}"
	done
	printf '%s\n' "${value}"
}

image_server_base_url() {
	local port="$1"
	local host="$2"
	local base_url="$3"

	if [[ -n "${base_url}" ]]; then
		trim_trailing_slash "${base_url}"
		return
	fi

	if [[ -z "${host}" || "${host}" == "auto" ]]; then
		host="$(primary_ipv4)"
	fi

	printf 'http://%s:%s\n' "${host}" "${port}"
}

validate_machine() {
	local machine="$1"
	[[ -n "${machine}" ]] || die "--machine is required"
	[[ "${machine}" =~ ^[A-Za-z0-9_.+-]+$ ]] || die "invalid machine name: ${machine}"
}

validate_channel() {
	local channel="$1"
	[[ -n "${channel}" ]] || die "cannot resolve feed channel"
	[[ "${channel}" =~ ^[a-z0-9][a-z0-9_-]{1,63}$ ]] || die "invalid feed channel: ${channel}"
}

validate_imagedir() {
	local imagedir="$1"
	[[ -n "${imagedir}" ]] || die "cannot resolve online image directory"
	[[ "${imagedir}" =~ ^[a-z0-9][a-z0-9_-]{1,63}$ ]] || die "invalid online image directory: ${imagedir}"
}

json_value() {
	local file="$1"
	local key_path="$2"
	python3 - "$file" "$key_path" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        value = json.load(fh)
    for part in sys.argv[2].split("."):
        if not part:
            continue
        if isinstance(value, dict):
            value = value.get(part, "")
        else:
            value = ""
            break
    if value is None:
        value = ""
    print(value)
except Exception:
    pass
PY
}

catalog_pair() {
	local catalog="$1"
	local machine="$2"
	local channel="$3"
	local imagedir="$4"
	[[ -f "${catalog}" ]] || return 1
	python3 - "$catalog" "$machine" "$channel" "$imagedir" <<'PY'
import json
import sys

catalog, machine, channel, imagedir = sys.argv[1:5]
try:
    with open(catalog, encoding="utf-8") as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)

items = data.get("items", [])
if not isinstance(items, list):
    sys.exit(1)

for item in items:
    if not isinstance(item, dict):
        continue
    item_channel = str(item.get("channel", ""))
    item_imagedir = str(item.get("imagedir", ""))
    item_machine = str(item.get("machine", ""))
    if machine and item_machine != machine and item_imagedir != machine:
        continue
    if channel and item_channel != channel:
        continue
    if imagedir and item_imagedir != imagedir:
        continue
    if item_channel and item_imagedir:
        print(f"{item_channel}\t{item_imagedir}")
        sys.exit(0)

sys.exit(1)
PY
}

default_channel() {
	local value="$1"
	case "${value}" in
		release|beta|nightly)
			printf '%s\n' "${value}"
			;;
		*)
			printf 'release\n'
			;;
	esac
}

resolve_feed_parts() {
	local machine="$1"
	local machinebuild="$2"
	local builddir="$3"
	local catalog="$4"
	local channel="$5"
	local imagedir="$6"

	local deploy_tmp=""
	local manifest_path=""
	local pair=""

	if [[ -x "${CLI}" && -n "${machine}" && -d "${builddir}" ]]; then
		deploy_tmp="$(mktemp)"
		local deploy_args=(deploy-info --machine "${machine}" --builddir "${builddir}" --require-images --json)
		if [[ -n "${machinebuild}" ]]; then
			deploy_args+=(--machinebuild "${machinebuild}")
		fi
		if "${CLI}" "${deploy_args[@]}" > "${deploy_tmp}" 2>/dev/null; then
			if [[ -z "${imagedir}" ]]; then
				imagedir="$(json_value "${deploy_tmp}" "online_imagedir")"
			fi
			manifest_path="$(json_value "${deploy_tmp}" "manifest")"
			if [[ -z "${channel}" && -f "${manifest_path}" ]]; then
				channel="$(json_value "${manifest_path}" "channel")"
			fi
		fi
		rm -f "${deploy_tmp}"
	fi

	if [[ -f "${catalog}" ]]; then
		if pair="$(catalog_pair "${catalog}" "${machine}" "${channel}" "${imagedir}" 2>/dev/null)"; then
			if [[ -z "${channel}" ]]; then
				channel="${pair%%$'\t'*}"
			fi
			if [[ -z "${imagedir}" ]]; then
				imagedir="${pair#*$'\t'}"
			fi
		fi
	fi

	if [[ -z "${channel}" ]]; then
		channel="$(default_channel "${DISTRO_TYPE:-release}")"
	fi

	validate_channel "${channel}"
	validate_imagedir "${imagedir}"
	printf '%s\t%s\n' "${channel}" "${imagedir}"
}

service_key_hint() {
	local local_key="${IMAGE_PORTAL_LOCAL_SERVICE_KEY:-LOCAL_SERVICE_KEY}"
	local enabled="${IMAGE_PORTAL_ENABLE_LOCAL_SERVICE_KEY:-1}"
	case "${enabled,,}" in
		0|false|no|off)
			local keys="${IMAGE_SERVER_SERVICE_KEYS:-${IMAGE_PORTAL_SERVICE_KEYS:-}}"
			printf '%s\n' "${keys%%,*}"
			;;
		*)
			printf '%s\n' "${local_key}"
			;;
	esac
}

feed_url() {
	local base_url="$1"
	local channel="$2"
	local imagedir="$3"
	printf '%s/feed/%s/%s\n' "${base_url}" "${channel}" "${imagedir}"
}

admin_webif_url() {
	local base_url="$1"
	local explicit="$2"
	local value

	if [[ -n "${explicit}" ]]; then
		value="$(trim_trailing_slash "${explicit}")"
		printf '%s/\n' "${value}"
		return
	fi

	printf '%s/admin/\n' "${base_url}"
}

do_url() {
	local machine="$1"
	local machinebuild="$2"
	local builddir="$3"
	local catalog="$4"
	local port="$5"
	local host="$6"
	local base_url="$7"
	local channel="$8"
	local imagedir="$9"
	local admin_url="${10}"

	validate_machine "${machine}"
	base_url="$(image_server_base_url "${port}" "${host}" "${base_url}")"

	local pair
	pair="$(resolve_feed_parts "${machine}" "${machinebuild}" "${builddir}" "${catalog}" "${channel}" "${imagedir}")"
	channel="${pair%%$'\t'*}"
	imagedir="${pair#*$'\t'}"

	local update_url
	update_url="$(feed_url "${base_url}" "${channel}" "${imagedir}")"
	if [[ -n "${admin_url}" || -d "${online_update_repo}/public/admin" ]]; then
		admin_url="$(admin_webif_url "${base_url}" "${admin_url}")"
	else
		admin_url=""
	fi
	local key
	key="$(service_key_hint)"

	printf 'image_update_url=%s\n' "${update_url}"
	printf 'image_manifest_file=manifest.json\n'
	if [[ -n "${key}" ]]; then
		printf 'image_service_key=%s\n' "${key}"
	fi
	printf '\n'
	printf 'manifest: %s/manifest.json\n' "${update_url}"
	if [[ -n "${key}" ]]; then
		printf "curl: curl -H 'X-Tuxbox-Service-Key: %s' '%s/manifest.json'\n" "${key}" "${update_url}"
	else
		printf "curl: curl '%s/manifest.json'\n" "${update_url}"
	fi
	printf 'logs: %s\n' "${LOG_DIR}"
	# Operator info only: this URL is opened in a browser, Neutrino does
	# not read it.
	if [[ -n "${admin_url}" ]]; then
		printf 'admin webif: %s\n' "${admin_url}"
	fi
}

do_start() {
	local machine="$1"
	local machinebuild="$2"
	local builddir="$3"
	local feed_root="$4"
	local catalog="$5"
	local online_update_repo="$6"
	local port="$7"
	local host="$8"
	local bind_addr="$9"
	local base_url="${10}"
	local channel="${11}"
	local imagedir="${12}"
	local admin_url="${13}"

	mkdir -p "${RUN_DIR}" "${LOG_DIR}"
	if is_running; then
		echo "image server already running (pid $(cat "${PID_FILE}"))"
		do_url "${machine}" "${machinebuild}" "${builddir}" "${catalog}" "${port}" "${host}" "${base_url}" "${channel}" "${imagedir}" "${admin_url}"
		return 0
	fi

	command -v php >/dev/null 2>&1 || die "php not found"
	[[ -d "${online_update_repo}" ]] || die "online-update repo not found: ${online_update_repo}"
	[[ -d "${online_update_repo}/public" ]] || die "missing public dir: ${online_update_repo}/public"
	[[ -f "${online_update_repo}/tools/dev-server-router.php" ]] || die "missing router: ${online_update_repo}/tools/dev-server-router.php"
	[[ -d "${feed_root}" ]] || die "feed root does not exist: ${feed_root}; run make image-server-stage first"
	[[ -f "${catalog}" ]] || die "catalog does not exist: ${catalog}; run make image-server-stage first"

	base_url="$(image_server_base_url "${port}" "${host}" "${base_url}")"
	feed_root="$(readlink -f "${feed_root}")"
	catalog="$(readlink -f "${catalog}")"
	online_update_repo="$(readlink -f "${online_update_repo}")"

	local local_key="${IMAGE_PORTAL_LOCAL_SERVICE_KEY:-LOCAL_SERVICE_KEY}"
	local enable_local_key="${IMAGE_PORTAL_ENABLE_LOCAL_SERVICE_KEY:-1}"
	local service_keys="${IMAGE_SERVER_SERVICE_KEYS:-${IMAGE_PORTAL_SERVICE_KEYS:-}}"
	if [[ -z "${service_keys}" ]]; then
		# Empty keys would disable auth entirely; a fixed placeholder would
		# itself be a well-known valid key. Use a random per-start key so
		# only the private-client LOCAL_SERVICE_KEY path authenticates.
		service_keys="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
		case "${enable_local_key,,}" in
			0|false|no|off)
				warn "local service key disabled and no IMAGE_SERVER_SERVICE_KEYS set; clients cannot authenticate"
				;;
		esac
	fi

	(
		cd "${online_update_repo}"
		export ONLINE_UPDATE_CATALOG="${catalog}"
		export ONLINE_UPDATE_ARTIFACT_BASE_PATH="${feed_root}"
		export ONLINE_UPDATE_ARTIFACT_BASE_URL="${base_url}/feed"
		export ONLINE_UPDATE_PORTAL_BASE_URL="${base_url}"
		export IMAGE_PORTAL_SERVICE_KEYS="${service_keys}"
		export IMAGE_PORTAL_LOCAL_SERVICE_KEY="${local_key}"
		export IMAGE_PORTAL_ENABLE_LOCAL_SERVICE_KEY="${enable_local_key}"
		export IMAGE_PORTAL_AUTH_LOG_FILE="${AUTH_LOG}"
		export IMAGE_PORTAL_AUTH_RATE_LIMIT_DIR="${RUN_DIR}/auth-ratelimit"
		if command -v setsid >/dev/null 2>&1; then
			exec setsid php -S "${bind_addr}:${port}" -t public tools/dev-server-router.php
		fi
		exec nohup php -S "${bind_addr}:${port}" -t public tools/dev-server-router.php
	) > "${PHP_LOG}" 2>&1 &

	local pid="$!"
	printf '%s\n' "${pid}" > "${PID_FILE}"
	sleep 0.4
	if ! kill -0 "${pid}" 2>/dev/null; then
		rm -f "${PID_FILE}"
		die "image server failed to start; see ${PHP_LOG}"
	fi

	local pair=""
	local update_url=""
	local resolved_admin_url=""
	if pair="$(resolve_feed_parts "${machine}" "${machinebuild}" "${builddir}" "${catalog}" "${channel}" "${imagedir}" 2>/dev/null)"; then
		channel="${pair%%$'\t'*}"
		imagedir="${pair#*$'\t'}"
		update_url="$(feed_url "${base_url}" "${channel}" "${imagedir}")"
	fi
	if [[ -n "${admin_url}" || -d "${online_update_repo}/public/admin" ]]; then
		resolved_admin_url="$(admin_webif_url "${base_url}" "${admin_url}")"
	fi

	{
		printf 'port=%s\n' "${port}"
		printf 'bind=%s\n' "${bind_addr}"
		printf 'base_url=%s\n' "${base_url}"
		[[ -n "${update_url}" ]] && printf 'update_url=%s\n' "${update_url}"
		[[ -n "${resolved_admin_url}" ]] && printf 'admin_webif_url=%s\n' "${resolved_admin_url}"
		printf 'catalog=%s\n' "${catalog}"
		printf 'feed_root=%s\n' "${feed_root}"
		printf 'online_update_repo=%s\n' "${online_update_repo}"
		printf 'php_log=%s\n' "${PHP_LOG}"
		printf 'auth_log=%s\n' "${AUTH_LOG}"
	} > "${META_FILE}"

	echo "image server started (backend=php, pid=${pid})"
	do_url "${machine}" "${machinebuild}" "${builddir}" "${catalog}" "${port}" "${host}" "${base_url}" "${channel}" "${imagedir}" "${admin_url}"
}

do_stop() {
	if [[ ! -f "${PID_FILE}" ]]; then
		echo "image server stopped"
		return
	fi
	local pid
	pid="$(tr -d '[:space:]' < "${PID_FILE}")"
	if [[ -z "${pid}" ]] || ! kill -0 "${pid}" 2>/dev/null; then
		rm -f "${PID_FILE}"
		echo "image server stopped"
		return
	fi
	if ! pid_is_image_server "${pid}"; then
		# PID was reused by an unrelated process; never kill it.
		rm -f "${PID_FILE}"
		echo "stale pid file removed (pid ${pid} is not the image server)"
		return
	fi
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
	echo "image server stopped"
}

do_status() {
	if is_running; then
		echo "image server running (pid $(cat "${PID_FILE}"))"
		[[ -f "${META_FILE}" ]] && sed 's/^/  /' "${META_FILE}"
	else
		echo "image server stopped"
	fi
}

cmd="${1:-}"
if [[ -z "${cmd}" ]]; then
	usage
	exit 1
fi
shift

machine="${MACHINE:-}"
machinebuild="${MACHINEBUILD:-}"
builddir="${BUILD_DIR:-${BUILDDIR:-}}"
feed_root="${PORTAL_FEED_ROOT:-${FEED_ROOT:-${TOPDIR}/portal-feed}}"
catalog="${PORTAL_CATALOG_OUT:-${CATALOG_OUT:-${feed_root}/catalog.json}}"
online_update_repo="${PORTAL_ONLINE_UPDATE_REPO:-${ONLINE_UPDATE_REPO:-${TOPDIR}/../online-update}}"
channel="${IMAGE_SERVER_CHANNEL:-}"
imagedir="${IMAGE_SERVER_IMAGEDIR:-}"
port="${IMAGE_SERVER_PORT:-33334}"
host="${IMAGE_SERVER_HOST:-auto}"
bind_addr="${IMAGE_SERVER_BIND:-0.0.0.0}"
base_url="${IMAGE_SERVER_BASE_URL:-}"
admin_url="${IMAGE_SERVER_ADMIN_WEBIF_URL:-}"

while [[ $# -gt 0 ]]; do
	case "$1" in
		--machine) machine="${2:-}"; shift 2 ;;
		--machinebuild) machinebuild="${2:-}"; shift 2 ;;
		--builddir) builddir="${2:-}"; shift 2 ;;
		--feed-root) feed_root="${2:-}"; shift 2 ;;
		--catalog) catalog="${2:-}"; shift 2 ;;
		--online-update-repo) online_update_repo="${2:-}"; shift 2 ;;
		--channel) channel="${2:-}"; shift 2 ;;
		--imagedir) imagedir="${2:-}"; shift 2 ;;
		--port) port="${2:-}"; shift 2 ;;
		--host) host="${2:-}"; shift 2 ;;
		--bind) bind_addr="${2:-}"; shift 2 ;;
		--base-url) base_url="${2:-}"; shift 2 ;;
		--admin-webif-url) admin_url="${2:-}"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) die "unknown option: $1" ;;
	esac
done

if [[ -z "${builddir}" ]]; then
	if [[ -n "${machine}" ]]; then
		builddir="${TOPDIR}/builds/${machine}"
	else
		builddir="${TOPDIR}/builds"
	fi
fi

case "${cmd}" in
	base-url)
		image_server_base_url "${port}" "${host}" "${base_url}"
		;;
	url)
		do_url "${machine}" "${machinebuild}" "${builddir}" "${catalog}" "${port}" "${host}" "${base_url}" "${channel}" "${imagedir}" "${admin_url}"
		;;
	start)
		do_start "${machine}" "${machinebuild}" "${builddir}" "${feed_root}" "${catalog}" "${online_update_repo}" "${port}" "${host}" "${bind_addr}" "${base_url}" "${channel}" "${imagedir}" "${admin_url}"
		;;
	stop)
		do_stop
		;;
	status)
		do_status
		;;
	*)
		usage
		exit 1
		;;
esac
