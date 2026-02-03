#!/usr/bin/env bash
set -euo pipefail

TOPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

SSH_HOST="${SSH_HOST:-127.0.0.1}"
SSH_PORT="${SSH_PORT:-2222}"
SSH_USER="${SSH_USER:-root}"
TIMEOUT="${TIMEOUT:-180}"
SHUTDOWN="${SHUTDOWN:-1}"
SKIP_PING="${SKIP_PING:-0}"
REQUIRED_UNITS="${REQUIRED_UNITS:-sshd}"
REQUIRED_SERVICES="${REQUIRED_SERVICES:-sshd}"
LOG_DIR="${LOG_DIR:-${TOPDIR}/build/qemu-logs}"

ssh_opts=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=5)
if [[ -n "${SSH_OPTS:-}" ]]; then
  read -r -a extra_opts <<< "${SSH_OPTS}"
  ssh_opts+=("${extra_opts[@]}")
fi
if [[ -n "${SSH_IDENTITY:-}" ]]; then
  ssh_opts+=(-i "${SSH_IDENTITY}")
fi

control_path="${LOG_DIR}/ssh-control-${SSH_PORT}.sock"

ssh_cmd() {
  ssh "${ssh_opts[@]}" -o ControlPath="${control_path}" -o ControlMaster=auto \
    -p "${SSH_PORT}" \
    "${SSH_USER}@${SSH_HOST}" "$@"
}

wait_for_ssh() {
  local deadline=$((SECONDS + TIMEOUT))
  while (( SECONDS < deadline )); do
    if (echo >"/dev/tcp/${SSH_HOST}/${SSH_PORT}") >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

wait_for_shutdown() {
  local deadline=$((SECONDS + TIMEOUT))
  while (( SECONDS < deadline )); do
    if ! (echo >"/dev/tcp/${SSH_HOST}/${SSH_PORT}") >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

mkdir -p "${LOG_DIR}"
stamp="$(date +%Y%m%d-%H%M%S)"
log_prefix="${LOG_DIR}/qemu-${stamp}"

echo "Waiting for SSH on ${SSH_HOST}:${SSH_PORT} (timeout ${TIMEOUT}s)..."
if ! wait_for_ssh; then
  echo "SSH did not become available." >&2
  exit 1
fi

cleanup_master() {
  ssh "${ssh_opts[@]}" -o ControlPath="${control_path}" -p "${SSH_PORT}" \
    -O exit "${SSH_USER}@${SSH_HOST}" >/dev/null 2>&1 || true
}
trap cleanup_master EXIT

ssh "${ssh_opts[@]}" -o ControlPath="${control_path}" -o ControlMaster=yes \
  -o ControlPersist=60 -p "${SSH_PORT}" -N -f "${SSH_USER}@${SSH_HOST}"

echo "SSH ready, running smoke checks..."
ssh_cmd "uname -a"
ssh_cmd "cat /etc/os-release"
ssh_cmd "ip addr show"
ssh_cmd "ip route show"
ssh_cmd "opkg --version"

if [[ "${SKIP_PING}" != "1" ]]; then
  ssh_cmd "ping -c1 -w5 192.168.7.1"
fi

if ssh_cmd "command -v systemctl >/dev/null 2>&1"; then
  ssh_cmd "systemctl is-system-running --wait || true"
  for unit in ${REQUIRED_UNITS}; do
    ssh_cmd "systemctl is-active ${unit}"
  done
  ssh_cmd "systemctl --no-pager --failed || true"
  ssh_cmd "journalctl -b --no-pager" > "${log_prefix}-journal.txt" || true
else
  for svc in ${REQUIRED_SERVICES}; do
    ssh_cmd "service ${svc} status || /etc/init.d/${svc} status"
  done
  ssh_cmd "test -f /var/log/messages && tail -n 200 /var/log/messages" \
    > "${log_prefix}-messages.txt" || true
fi

ssh_cmd "dmesg" > "${log_prefix}-dmesg.txt" || true
ssh_cmd "ps -eo pid,comm,args --sort=comm" > "${log_prefix}-ps.txt" || true

if [[ "${SHUTDOWN}" == "1" ]]; then
  echo "Requesting poweroff..."
  ssh_cmd "poweroff" || true
  if ! wait_for_shutdown; then
    echo "Shutdown did not complete within ${TIMEOUT}s." >&2
    exit 1
  fi
  echo "Shutdown complete."
fi

echo "Smoke test complete. Logs: ${LOG_DIR}"
