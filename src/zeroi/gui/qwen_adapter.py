import logging
from typing import Any

import httpx

from ..config import settings
from ..errors import ExecutionError
from ..schemas import GUIBatch, Observation

log = logging.getLogger(__name__)


class QwenUIAgentAdapter:
    """
    Adapter for the official open-source Qwen-UI-Agent.

    zeroi does not reimplement Qwen-UI-Agent. This adapter expects Qwen-UI-Agent
    to be exposed as an HTTP execution service. If the official repository provides
    a different API, implement a driver here and keep zeroi orchestration unchanged.
    """

    def __init__(self) -> None:
        self.base_url = settings.qwen_ui_agent_url.rstrip("/")
        self.timeout = settings.qwen_timeout
        self.headers = {"Content-Type": "application/json"}
        if settings.qwen_ui_agent_api_key:
            self.headers["Authorization"] = f"Bearer {settings.qwen_ui_agent_api_key}"

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/healthz", headers=self.headers)
                return resp.status_code == 200
        except Exception:
            return False

    async def perceive(self, device: dict[str, Any] | None) -> Observation:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/perceive",
                    headers=self.headers,
                    json={"device": device},
                )
                resp.raise_for_status()
                return Observation.model_validate(resp.json())
        except Exception as exc:
            log.warning("Qwen perceive failed: %s", exc)
            return Observation()

    async def execute_goal(self, objective: str, device: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "mode": "goal",
            "objective": objective,
            "device": device,
            "context": context,
            "batching": True,
            "vision_grounding": True,
            "recovery": True,
        }
        return await self._post_execute(payload)

    async def execute_batch(self, batch: GUIBatch, context: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "mode": "batch",
            "batch": batch.model_dump(mode="json"),
            "context": context,
            "vision_grounding": True,
        }
        return await self._post_execute(payload)

    async def _post_execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/execute",
                    headers=self.headers,
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            raise ExecutionError(f"Qwen UI Agent HTTP error: {exc.response.status_code}: {exc.response.text}") from exc
        except Exception as exc:
            raise ExecutionError(f"Qwen UI Agent execution failed: {exc}") from exc
