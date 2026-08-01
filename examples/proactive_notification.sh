#!/usr/bin/env bash
set -euo pipefail

NOTIFICATION_URL="${NOTIFICATION_URL:-http://localhost:8105}"

curl -X POST "$NOTIFICATION_URL/v1/notifications" \
  -H 'Content-Type: application/json' \
  -d '{
        "source": "email",
        "title": "Flight check-in reminder",
        "body": "Your flight BA117 check-in opens in 24 hours.",
        "raw": {
          "provider": "gmail",
          "labels": ["travel"]
        }
      }'
