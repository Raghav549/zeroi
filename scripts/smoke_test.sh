#!/usr/bin/env bash
set -euo pipefail

HARNESS_URL="${HARNESS_URL:-http://localhost:8100}"

echo "Checking harness health..."
curl -fsS "$HARNESS_URL/healthz"

echo
echo "Creating test request..."
RESPONSE=$(curl -fsS -X POST "$HARNESS_URL/v1/requests" \
  -H 'Content-Type: application/json' \
  -d '{"goal":"Smoke test: summarize zeroi architecture"}')

echo "$RESPONSE"

SESSION_ID=$(echo "$RESPONSE" | python -c 'import sys,json; print(json.load(sys.stdin)["session_id"])')

echo
echo "Checking session: $SESSION_ID"
curl -fsS "$HARNESS_URL/v1/sessions/$SESSION_ID"

echo
echo "Smoke test complete"
