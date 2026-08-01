#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
import os
import socket
import time
from urllib.parse import urlparse

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost:5432/zeroi")


def wait_for(host: str, port: int, name: str, timeout: int = 60) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"{name} ready at {host}:{port}")
                return
        except OSError:
            print(f"waiting for {name} at {host}:{port}")
            time.sleep(1)
    raise SystemExit(f"{name} not ready after {timeout}s")


redis = urlparse(REDIS_URL)
wait_for(redis.hostname or "localhost", redis.port or 6379, "redis")

db = urlparse(DATABASE_URL.replace("+asyncpg", "").replace("+aiosqlite", ""))
if db.scheme.startswith("postgres"):
    wait_for(db.hostname or "localhost", db.port or 5432, "postgres")
else:
    print("using sqlite; no database wait required")
PY
