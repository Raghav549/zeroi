#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${1:-harness}"

bash scripts/wait_for_deps.sh

exec python -m zeroi "$SERVICE_NAME"
