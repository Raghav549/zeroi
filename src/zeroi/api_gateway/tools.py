import os
from typing import Any

import httpx

from ..errors import ExecutionError

TOOL_REGISTRY = {
    "http_get": {"method": "GET"},
    "http_post": {"method": "POST"},
}


async def execute_api(spec: dict[str, Any]) -> dict[str, Any]:
    tool = spec.get("tool", "http_get")
    if tool not in TOOL_REGISTRY:
        raise ExecutionError(f"unknown API tool: {tool}")

    method = spec.get("method", TOOL_REGISTRY[tool]["method"])
    url = spec.get("url")
    if not url:
        raise ExecutionError("API spec missing url")

    headers = spec.get("headers", {})
    auth_secret = spec.get("auth_secret")
    if auth_secret:
        headers["Authorization"] = f"Bearer {os.getenv(auth_secret, '')}"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.request(
            method,
            url,
            headers=headers,
            params=spec.get("params"),
            json=spec.get("json"),
            data=spec.get("data"),
        )

    return {
        "status": resp.status_code,
        "json": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None,
        "text": resp.text[:20000],
    }
