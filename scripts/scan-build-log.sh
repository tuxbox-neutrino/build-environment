#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scan-build-log.sh [--log <file> | --glob <pattern>] [options]

Options:
  --log <file>            Explicit log file to scan.
  --glob <pattern>        Glob to resolve latest log file.
                          Default: builds/build/tmp-*/log/cooker/*/*.log
  --report <file>         Write Markdown report to file.
  --metrics <file>        Write key=value metrics to file.
  --max-lines <N>         Max lines per excerpt section (default: 20).
  --allow-missing         Succeed if no log file is found.
  --no-fail-on-critical   Do not fail even when critical lines are found.
  -h, --help              Show this help.
EOF
}

LOG_FILE=""
LOG_GLOB="builds/build/tmp-*/log/cooker/*/*.log"
REPORT_FILE=""
METRICS_FILE=""
ALLOW_MISSING="0"
FAIL_ON_CRITICAL="1"
MAX_LINES="20"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --log)
      LOG_FILE="${2:-}"
      shift 2
      ;;
    --glob)
      LOG_GLOB="${2:-}"
      shift 2
      ;;
    --report)
      REPORT_FILE="${2:-}"
      shift 2
      ;;
    --metrics)
      METRICS_FILE="${2:-}"
      shift 2
      ;;
    --max-lines)
      MAX_LINES="${2:-}"
      shift 2
      ;;
    --allow-missing)
      ALLOW_MISSING="1"
      shift
      ;;
    --no-fail-on-critical)
      FAIL_ON_CRITICAL="0"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "${LOG_FILE}" ]]; then
  shopt -s nullglob
  # shellcheck disable=SC2206
  matches=( ${LOG_GLOB} )
  shopt -u nullglob
  if [[ ${#matches[@]} -gt 0 ]]; then
    # shellcheck disable=SC2012
    LOG_FILE="$(ls -1t "${matches[@]}" | head -n1)"
  fi
fi

if [[ -z "${LOG_FILE}" || ! -f "${LOG_FILE}" ]]; then
  msg="No build log found (glob: ${LOG_GLOB})"
  if [[ "${ALLOW_MISSING}" == "1" ]]; then
    echo "INFO: ${msg}"
    if [[ -n "${METRICS_FILE}" ]]; then
      cat >"${METRICS_FILE}" <<EOF
critical_count=0
warning_count=0
critical_present=false
warning_present=false
critical_fingerprint=none
log_path=none
EOF
    fi
    if [[ -n "${REPORT_FILE}" ]]; then
      cat >"${REPORT_FILE}" <<EOF
# Build Log Scan

- status: no log found
- glob: \`${LOG_GLOB}\`
EOF
    fi
    exit 0
  fi
  echo "ERROR: ${msg}" >&2
  exit 2
fi

critical_pattern='ERROR:|basehash value changed|Taskhash mismatch|nondeterministic and this needs to be fixed|Failed to run qemu'
warning_pattern='WARNING:|patch-fuzz|QA Issue: Fuzz detected'

critical_hits="$(rg -n -e "${critical_pattern}" "${LOG_FILE}" || true)"
warning_hits="$(rg -n -e "${warning_pattern}" "${LOG_FILE}" || true)"

critical_count="$(printf '%s\n' "${critical_hits}" | sed '/^$/d' | wc -l | tr -d ' ')"
warning_count="$(printf '%s\n' "${warning_hits}" | sed '/^$/d' | wc -l | tr -d ' ')"

critical_present="false"
warning_present="false"
if [[ "${critical_count}" != "0" ]]; then
  critical_present="true"
fi
if [[ "${warning_count}" != "0" ]]; then
  warning_present="true"
fi

fingerprint_source="$(printf '%s\n' "${critical_hits}" | head -n 20)"
if [[ -n "${fingerprint_source}" ]]; then
  critical_fingerprint="$(printf '%s' "${fingerprint_source}" | sha256sum | awk '{print $1}')"
else
  critical_fingerprint="none"
fi

echo "Build log scan:"
echo "- log: ${LOG_FILE}"
echo "- critical_count: ${critical_count}"
echo "- warning_count: ${warning_count}"
if [[ "${critical_count}" != "0" ]]; then
  echo "- critical_fingerprint: ${critical_fingerprint}"
fi

if [[ -n "${METRICS_FILE}" ]]; then
  cat >"${METRICS_FILE}" <<EOF
critical_count=${critical_count}
warning_count=${warning_count}
critical_present=${critical_present}
warning_present=${warning_present}
critical_fingerprint=${critical_fingerprint}
log_path=${LOG_FILE}
EOF
fi

if [[ -n "${REPORT_FILE}" ]]; then
  {
    echo "# Build Log Scan"
    echo
    echo "- log: \`${LOG_FILE}\`"
    echo "- critical_count: ${critical_count}"
    echo "- warning_count: ${warning_count}"
    echo "- critical_fingerprint: \`${critical_fingerprint}\`"
    echo
    echo "## Critical Excerpt"
    if [[ "${critical_count}" != "0" ]]; then
      echo
      echo '```text'
      printf '%s\n' "${critical_hits}" | head -n "${MAX_LINES}"
      echo '```'
    else
      echo
      echo "_none_"
    fi
    echo
    echo "## Warning Excerpt"
    if [[ "${warning_count}" != "0" ]]; then
      echo
      echo '```text'
      printf '%s\n' "${warning_hits}" | head -n "${MAX_LINES}"
      echo '```'
    else
      echo
      echo "_none_"
    fi
  } >"${REPORT_FILE}"
fi

if [[ "${FAIL_ON_CRITICAL}" == "1" && "${critical_count}" != "0" ]]; then
  exit 3
fi

exit 0
