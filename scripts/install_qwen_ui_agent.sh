#!/usr/bin/env bash
set -euo pipefail

# Use the official Qwen-UI-Agent repository.
# If your official fork/org differs, set QWEN_UI_AGENT_REPO.
QWEN_UI_AGENT_REPO="${QWEN_UI_AGENT_REPO:-https://github.com/QwenLM/Qwen-UI-Agent.git}"
QWEN_UI_AGENT_DIR="${QWEN_UI_AGENT_DIR:-./vendor/qwen-ui-agent}"

mkdir -p vendor

if [ ! -d "$QWEN_UI_AGENT_DIR" ]; then
  git clone "$QWEN_UI_AGENT_REPO" "$QWEN_UI_AGENT_DIR"
fi

cd "$QWEN_UI_AGENT_DIR"

python -m pip install -U pip
python -m pip install -e . || echo "Install Qwen-UI-Agent dependencies according to its official README."

echo ""
echo "Qwen-UI-Agent vendored at: $QWEN_UI_AGENT_DIR"
echo "Run its official inference/server entrypoint and expose it to zeroi via QWEN_UI_AGENT_URL."
