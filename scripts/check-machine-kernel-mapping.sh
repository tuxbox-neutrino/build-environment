#!/usr/bin/env bash
set -euo pipefail

TOPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${TOPDIR}/cli.py" audit-machine-mapping "$@"
