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
# Persistent local service key: sibling of run/ on purpose — run/ holds
# per-run state, the key must survive restarts. image-server/ is gitignored.
SERVICE_KEY_FILE="${IMAGE_SERVER_DIR}/service-key"

usage() {
	cat <<'EOF'
Usage: scripts/image-server.sh <command> [options]

Commands:
  start     Start the local PHP image server from the online-update repo
  stop      Stop the local image server
  status    Show local image server status
  url       Print Neutrino image_update_url and test curl command
  base-url  Print the image server base URL
  key       Print the effective local service key (creates one if missing)
  key set <value>
            Set the persistent local service key

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

# --- service key ------------------------------------------------------------
# One persistent local key closes the loop image build -> local portal: the
# same value is baked into /etc/image-version (make config) and seeded into
# the portal as its opt-in local service key. The portal hard-rejects the
# documented example value LOCAL_SERVICE_KEY, and Neutrino discards X-only
# values as placeholders — both count as unusable on this side too.

service_key_valid() {
	# Shell-safe charset on purpose: the key is printed into copy-paste
	# curl lines and passed through make; generated keys are 32 hex chars.
	[[ "$1" =~ ^[A-Za-z0-9._-]{8,64}$ ]]
}

service_key_unusable() {
	[[ "$1" == "LOCAL_SERVICE_KEY" || "$1" =~ ^[Xx]{8,}$ ]]
}

local_key_enabled() {
	# Exactly the portal's boolean parsing: only these values enable.
	local v="${IMAGE_PORTAL_ENABLE_LOCAL_SERVICE_KEY:-1}"
	case "${v,,}" in
		1|true|yes|on) return 0 ;;
		*) return 1 ;;
	esac
}

service_key_read_file() {
	# '' when absent; a broken file is an error, never silently regenerated.
	if [[ ! -e "${SERVICE_KEY_FILE}" && ! -L "${SERVICE_KEY_FILE}" ]]; then
		return 0
	fi
	if [[ -L "${SERVICE_KEY_FILE}" || ! -f "${SERVICE_KEY_FILE}" ]]; then
		die "service key is not a regular file: ${SERVICE_KEY_FILE}"
	fi
	local value
	value="$(tr -d '[:space:]' < "${SERVICE_KEY_FILE}")"
	service_key_valid "${value}" || die "service key file has an invalid value (allowed: A-Za-z0-9._- with 8-64 chars): ${SERVICE_KEY_FILE}"
	if service_key_unusable "${value}"; then
		die "service key file holds a value that never authenticates (example value or X-only placeholder): ${SERVICE_KEY_FILE}"
	fi
	chmod 600 "${SERVICE_KEY_FILE}" 2>/dev/null || true
	printf '%s\n' "${value}"
}

service_key_write_file() {
	# Atomic replace with a same-content no-op: status/url canonicalize on
	# every resolution and must not bump the inode the rotation warning
	# compares.
	local value="$1"
	service_key_valid "${value}" || die "invalid service key (allowed: A-Za-z0-9._- with 8-64 chars)"
	if service_key_unusable "${value}"; then
		die "unusable service key: the example value and X-only placeholders never authenticate"
	fi
	local current=""
	if [[ -f "${SERVICE_KEY_FILE}" && ! -L "${SERVICE_KEY_FILE}" ]]; then
		current="$(tr -d '[:space:]' < "${SERVICE_KEY_FILE}" 2>/dev/null || true)"
	fi
	if [[ "${current}" == "${value}" ]]; then
		return 0
	fi
	mkdir -p "${IMAGE_SERVER_DIR}"
	local tmp
	tmp="$(umask 077 && mktemp "${IMAGE_SERVER_DIR}/.service-key.XXXXXX")" || die "cannot create temp file in ${IMAGE_SERVER_DIR}"
	printf '%s\n' "${value}" > "${tmp}"
	chmod 600 "${tmp}"
	mv -f "${tmp}" "${SERVICE_KEY_FILE}"
}

ensure_service_key() {
	# Create-if-absent. Parallel-safe: the hard link succeeds for exactly
	# one racer; the loser removes its temp file and adopts the winner's key.
	local value
	value="$(service_key_read_file)"
	if [[ -n "${value}" ]]; then
		printf '%s\n' "${value}"
		return 0
	fi
	mkdir -p "${IMAGE_SERVER_DIR}"
	local tmp new
	new="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
	tmp="$(umask 077 && mktemp "${IMAGE_SERVER_DIR}/.service-key.XXXXXX")" || die "cannot create temp file in ${IMAGE_SERVER_DIR}"
	printf '%s\n' "${new}" > "${tmp}"
	chmod 600 "${tmp}"
	if ! ln "${tmp}" "${SERVICE_KEY_FILE}" 2>/dev/null; then
		rm -f "${tmp}"
		value="$(service_key_read_file)"
		[[ -n "${value}" ]] || die "cannot create ${SERVICE_KEY_FILE}"
		printf '%s\n' "${value}"
		return 0
	fi
	rm -f "${tmp}"
	printf '%s\n' "${new}"
}

effective_service_key() {
	# THE resolver: start seeding, url/status display and the `key`
	# subcommand (which make config bakes from) all go through here. A
	# usable local-key result is canonicalized into SERVICE_KEY_FILE, so
	# separate invocations agree even after environment variables change.
	# Output: '<tag>\t<value>' with tag generated|env-local|env-keys|none.
	if local_key_enabled; then
		local envkey="${IMAGE_PORTAL_LOCAL_SERVICE_KEY:-}"
		if [[ -n "${envkey}" ]]; then
			if service_key_valid "${envkey}" && ! service_key_unusable "${envkey}"; then
				service_key_write_file "${envkey}"
				printf 'env-local\t%s\n' "${envkey}"
				return 0
			fi
			warn "IMAGE_PORTAL_LOCAL_SERVICE_KEY is unusable (example value, X-only placeholder or bad charset); using ${SERVICE_KEY_FILE}"
		fi
		local generated
		generated="$(ensure_service_key)"
		printf 'generated\t%s\n' "${generated}"
		return 0
	fi
	local keys="${IMAGE_SERVER_SERVICE_KEYS:-${IMAGE_PORTAL_SERVICE_KEYS:-}}"
	local entry
	while IFS= read -r entry; do
		entry="${entry#"${entry%%[![:space:]]*}"}"
		entry="${entry%"${entry##*[![:space:]]}"}"
		[[ -n "${entry}" ]] || continue
		if service_key_unusable "${entry}"; then
			warn "ignoring an unusable service key from the environment (example value or X-only placeholder)"
			continue
		fi
		warn "local service key disabled: using an environment key that is not persisted (${SERVICE_KEY_FILE} stays untouched)"
		printf 'env-keys\t%s\n' "${entry}"
		return 0
	done <<< "${keys//,/$'\n'}"
	printf 'none\t\n'
}

service_key_stat() {
	stat -c '%d:%i:%Y:%s' "${SERVICE_KEY_FILE}" 2>/dev/null || printf 'missing\n'
}

meta_get() {
	[[ -f "${META_FILE}" ]] || return 0
	sed -n "s/^$1=//p" "${META_FILE}" | head -n 1
}

service_key_conf_check() {
	# Compare each machine's baked TUXBOX_SERVICE_KEY line with the
	# effective key. Honest wording: this reads the CURRENT config — it
	# proves what a rebuild would bake, never what an existing image was
	# built with (only /etc/image-version inside a built image knows that).
	local effective="$1"
	local inc value machine
	for inc in "${TOPDIR}"/builds/*/conf/local-image-server.inc; do
		[[ -f "${inc}" ]] || continue
		value="$(sed -n 's/^TUXBOX_SERVICE_KEY ?= "\(.*\)"$/\1/p' "${inc}" | head -n 1)"
		[[ -n "${value}" ]] || continue
		if [[ "${value}" != "${effective}" ]]; then
			machine="$(basename "$(dirname "$(dirname "${inc}")")")"
			warn "${machine}: the current config would bake '${value}' while the server key is '${effective}' — run 'make config MACHINE=${machine}', then rebuild"
		fi
	done
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

# (the former service_key_hint() printed the literal example value the
# portal rejects; every consumer now goes through effective_service_key)

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
	local key_tag key_value
	IFS=$'\t' read -r key_tag key_value < <(effective_service_key)
	local show_key=1
	local key_note=""
	if is_running; then
		# Never print an unverifiable key as copy-paste truth: a running
		# server keeps the environment it was started with.
		local started_source started_stat
		started_source="$(meta_get service_key_source)"
		started_stat="$(meta_get service_key_stat)"
		case "${key_tag}" in
			generated|env-local)
				if [[ "${started_source}" == "env-keys" || "${started_stat}" != "$(service_key_stat)" ]]; then
					show_key=0
					key_note="the running server was started with a different key — restart it (make image-server-stop && make image-server-start) to apply the current one"
				fi
				;;
			env-keys)
				show_key=0
				key_note="local service key disabled and the running server's environment keys cannot be verified — restart with the current environment, or re-enable the local key"
				;;
			none)
				show_key=0
				key_note="no usable service key: local key disabled and no IMAGE_SERVER_SERVICE_KEYS set — boxes get 401/403 on key-gated channels"
				;;
		esac
	else
		case "${key_tag}" in
			env-keys)
				key_note="environment key, not persisted — ${SERVICE_KEY_FILE} stays unused while the local key is disabled"
				;;
			none)
				show_key=0
				key_note="no usable service key: local key disabled and no IMAGE_SERVER_SERVICE_KEYS set — boxes get 401/403 on key-gated channels"
				;;
		esac
	fi
	if [[ -z "${key_value}" ]]; then
		show_key=0
	fi

	printf 'image_update_url=%s\n' "${update_url}"
	printf 'image_manifest_file=manifest.json\n'
	if [[ "${show_key}" == 1 ]]; then
		printf 'image_service_key=%s\n' "${key_value}"
	fi
	printf '\n'
	if [[ -n "${key_note}" ]]; then
		printf 'service key: %s\n' "${key_note}"
	fi
	printf 'manifest: %s/manifest.json\n' "${update_url}"
	if [[ "${show_key}" == 1 ]]; then
		printf "curl: curl -H 'X-Tuxbox-Service-Key: %s' '%s/manifest.json'\n" "${key_value}" "${update_url}"
	else
		printf "curl: curl '%s/manifest.json'\n" "${update_url}"
	fi
	case "${key_tag}" in
		generated|env-local)
			service_key_conf_check "${key_value}"
			;;
	esac
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

	local key_tag key_value
	IFS=$'\t' read -r key_tag key_value < <(effective_service_key)
	local local_key=""
	local enable_local_key="${IMAGE_PORTAL_ENABLE_LOCAL_SERVICE_KEY:-1}"
	case "${key_tag}" in
		generated|env-local)
			# Seed the portal's opt-in local key with the persisted value —
			# the same one make config bakes into /etc/image-version. The
			# former default seeded the literal example value, which the
			# portal hard-rejects.
			local_key="${key_value}"
			;;
	esac
	local service_keys="${IMAGE_SERVER_SERVICE_KEYS:-${IMAGE_PORTAL_SERVICE_KEYS:-}}"
	if [[ -z "${service_keys}" ]]; then
		# Empty keys would disable auth entirely; a fixed placeholder would
		# itself be a well-known valid key. Use a random per-start key so
		# only the local-service-key path authenticates.
		service_keys="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
		if [[ "${key_tag}" == "none" ]]; then
			warn "local service key disabled and no IMAGE_SERVER_SERVICE_KEYS set; clients cannot authenticate"
		fi
	fi
	local key_stat="-"
	case "${key_tag}" in
		generated|env-local)
			key_stat="$(service_key_stat)"
			;;
	esac

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
		# Keep the admin WebIF state in the writable per-run dir. Without this
		# the paths default to /etc/image-portal/*.json, which the unprivileged
		# dev server cannot create, so the admin/admin bootstrap user is never
		# seeded and first login fails with "Username or password is incorrect".
		export IMAGE_PORTAL_ADMIN_USERS_FILE="${IMAGE_PORTAL_ADMIN_USERS_FILE:-${RUN_DIR}/admin/users.json}"
		export IMAGE_PORTAL_ADMIN_KEYS_FILE="${IMAGE_PORTAL_ADMIN_KEYS_FILE:-${RUN_DIR}/admin/keys.json}"
		export IMAGE_PORTAL_ADMIN_FEED_ROOTS_FILE="${IMAGE_PORTAL_ADMIN_FEED_ROOTS_FILE:-${RUN_DIR}/admin/feed-roots.json}"
		export IMAGE_PORTAL_ADMIN_SETTINGS_FILE="${IMAGE_PORTAL_ADMIN_SETTINGS_FILE:-${RUN_DIR}/admin/settings.json}"
		export IMAGE_PORTAL_ADMIN_SOURCES_FILE="${IMAGE_PORTAL_ADMIN_SOURCES_FILE:-${RUN_DIR}/admin/sources.json}"
		export IMAGE_PORTAL_ADMIN_CHANNELS_FILE="${IMAGE_PORTAL_ADMIN_CHANNELS_FILE:-${RUN_DIR}/admin/channels.json}"
		export IMAGE_PORTAL_ADMIN_IPK_FEEDS_FILE="${IMAGE_PORTAL_ADMIN_IPK_FEEDS_FILE:-${RUN_DIR}/admin/ipk-feeds.json}"
		export IMAGE_PORTAL_ADMIN_LOGIN_RATE_LIMIT_DIR="${IMAGE_PORTAL_ADMIN_LOGIN_RATE_LIMIT_DIR:-${RUN_DIR}/admin-login-ratelimit}"
		export IMAGE_PORTAL_ADMIN_REBUILD_STATUS_DIR="${IMAGE_PORTAL_ADMIN_REBUILD_STATUS_DIR:-${RUN_DIR}/admin-rebuild-status}"
		# Mirror cache for the sync engine: the default is
		# /var/lib/image-portal/mirror, which the unprivileged dev server
		# cannot write — health then reports mirror_writable=false (503).
		# Local serving itself uses ONLINE_UPDATE_ARTIFACT_BASE_PATH above.
		export IMAGE_PORTAL_MIRROR_BASE_PATH="${IMAGE_PORTAL_MIRROR_BASE_PATH:-${RUN_DIR}/mirror}"
		mkdir -p "${IMAGE_PORTAL_MIRROR_BASE_PATH}" || warn "cannot create mirror dir: ${IMAGE_PORTAL_MIRROR_BASE_PATH}"
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
		# Key state markers, never the secret: this file is what gets pasted
		# into bug reports. The stat marker lets status/url detect a rotated
		# key file without an offline-crackable hash of short custom keys.
		printf 'service_key_source=%s\n' "${key_tag}"
		printf 'service_key_file=%s\n' "${SERVICE_KEY_FILE}"
		printf 'service_key_stat=%s\n' "${key_stat}"
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
		local started_source
		started_source="$(meta_get service_key_source)"
		case "${started_source}" in
			generated|env-local)
				if [[ "$(meta_get service_key_stat)" != "$(service_key_stat)" ]]; then
					echo "  service key: possibly CHANGED since start — restart to apply (make image-server-stop && make image-server-start)"
				else
					echo "  service key: unchanged since start (${started_source})"
				fi
				;;
			env-keys)
				echo "  service key: environment keys (the started value is not reconstructable)"
				;;
			none)
				echo "  service key: none (random fail-closed backstop only)"
				;;
		esac
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

# `key` takes subcommands, not the server options the loop below parses.
if [[ "${cmd}" == "key" ]]; then
	sub="${1:-}"
	case "${sub}" in
		"")
			IFS=$'\t' read -r key_tag key_value < <(effective_service_key)
			[[ -n "${key_value}" ]] || die "no usable service key (local key disabled and no usable environment key)"
			printf '%s\n' "${key_value}"
			;;
		set)
			[[ -n "${2:-}" ]] || die "usage: scripts/image-server.sh key set <value>"
			service_key_write_file "$2"
			if is_running && [[ "$(meta_get service_key_source)" =~ ^(generated|env-local)$ ]] \
				&& [[ "$(meta_get service_key_stat)" != "$(service_key_stat)" ]]; then
				warn "server is running with the previous key — restart to apply (make image-server-stop && make image-server-start)"
			fi
			printf '%s\n' "$2"
			;;
		*)
			die "unknown key subcommand: ${sub}"
			;;
	esac
	exit 0
fi

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
