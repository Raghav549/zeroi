#!/usr/bin/env bash
set -euo pipefail

HARNESS_URL="${HARNESS_URL:-http://localhost:8100}"

echo "Example 1: DeepSearch request"
curl -X POST "$HARNESS_URL/v1/requests" \
  -H 'Content-Type: application/json' \
  -d '{
        "goal": "Research the official Qwen-UI-Agent repository and summarize its architecture"
      }'

echo
echo "Example 2: CLI request"
curl -X POST "$HARNESS_URL/v1/requests" \
  -H 'Content-Type: application/json' \
  -d '{
        "goal": "Create a folder called reports and write a readme file"
      }'

echo
echo "Example 3: Browser request"
curl -X POST "$HARNESS_URL/v1/requests" \
  -H 'Content-Type: application/json' \
  -d '{
        "goal": "Open https://example.com and extract the main heading",
        "context": {
          "url": "https://example.com"
        }
      }'

echo
echo "Example 4: GUI request"
curl -X POST "$HARNESS_URL/v1/requests" \
  -H 'Content-Type: application/json' \
  -d '{
        "goal": "Open the system file manager and create a new folder named zeroi",
        "context": {
          "device": {
            "device_id": "local-desktop",
            "display_id": "primary"
          }
        }
      }'
