import logging
from typing import Any

import httpx

from ..config import settings
from ..llm import LLMClient

log = logging.getLogger(__name__)


class DeepSearchEngine:
    def __init__(self) -> None:
        self.llm = LLMClient()

    async def run(self, objective: str, max_rounds: int = 2, context: dict[str, Any] | None = None) -> dict[str, Any]:
        queries = await self.plan_queries(objective, context or {})
        evidence: list[dict[str, Any]] = []

        for round_idx in range(max_rounds):
            for query in queries:
                results = await self.search(query)
                evidence.extend(results)

            if len(evidence) >= 5:
                break

            queries = await self.refine_queries(objective, evidence)

        answer = await self.synthesize(objective, evidence)
        return {
            "objective": objective,
            "answer": answer.get("answer", ""),
            "target": answer.get("target"),
            "confidence": answer.get("confidence", 0.5),
            "citations": answer.get("citations", []),
            "evidence_count": len(evidence),
            "evidence": evidence[:20],
        }

    async def plan_queries(self, objective: str, context: dict[str, Any]) -> list[str]:
        messages = [
            {
                "role": "system",
                "content": "Generate search queries as JSON: {\"queries\": [\"...\"]}",
            },
            {"role": "user", "content": f"Objective: {objective}\nContext: {context}"},
        ]
        data = await self.llm.chat_json(messages)
        queries = data.get("queries")
        if queries:
            return queries[:5]
        return [objective]

    async def refine_queries(self, objective: str, evidence: list[dict[str, Any]]) -> list[str]:
        messages = [
            {
                "role": "system",
                "content": "Given evidence gaps, generate better search queries as JSON: {\"queries\": []}",
            },
            {
                "role": "user",
                "content": f"Objective: {objective}\nEvidence: {evidence[:10]}",
            },
        ]
        data = await self.llm.chat_json(messages)
        return data.get("queries", [objective])[:5]

    async def search(self, query: str) -> list[dict[str, Any]]:
        if settings.search_provider == "searxng":
            return await self.search_searxng(query)
        if settings.search_provider == "serper" and settings.serper_api_key:
            return await self.search_serper(query)
        return [{"title": "mock", "url": "about:blank", "snippet": query}]

    async def search_searxng(self, query: str) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    settings.searxng_url + "/search",
                    params={"q": query, "format": "json"},
                )
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "title": r.get("title"),
                        "url": r.get("url"),
                        "snippet": r.get("content"),
                    }
                    for r in data.get("results", [])[:10]
                ]
        except Exception:
            log.exception("searxng search failed")
            return []

    async def search_serper(self, query: str) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": settings.serper_api_key},
                    json={"q": query},
                )
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "title": r.get("title"),
                        "url": r.get("link"),
                        "snippet": r.get("snippet"),
                    }
                    for r in data.get("organic", [])[:10]
                ]
        except Exception:
            log.exception("serper search failed")
            return []

    async def synthesize(self, objective: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are DeepSearch. Compare sources, verify evidence, and return JSON: "
                    "{\"answer\": str, \"target\": str|null, \"confidence\": float, \"citations\": [str]}"
                ),
            },
            {"role": "user", "content": f"Objective: {objective}\nEvidence: {evidence}"},
        ]
        return await self.llm.chat_json(messages)
