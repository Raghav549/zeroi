#!/usr/bin/env bash
set -euo pipefail

mkdir -p .data/artifacts .data/workspaces

python -m venv .venv
source .venv/bin/activate

pip install -U pip
pip install -e ".[dev]"

playwright install chromium || true

echo "zeroi bootstrap complete"
