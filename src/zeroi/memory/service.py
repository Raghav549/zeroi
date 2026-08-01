from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from ..db import SessionLocal
from ..models import MemoryRecord
from ..schemas import MemoryQuery, MemoryRecordModel, MemoryWrite
from ..security import require_auth


class MemoryService:
    def __init__(self) -> None:
        self.router = APIRouter()
        self._register_routes()

    def _register_routes(self) -> None:
        @self.router.post("/v1/memories")
        async def write_memory(body: MemoryWrite, _=Depends(require_auth)):
            record = await self.write(body)
            return record

        @self.router.post("/v1/memories/query")
        async def query_memory(body: MemoryQuery, _=Depends(require_auth)):
            return await self.query(body)

    async def write(self, body: MemoryWrite) -> dict[str, Any]:
        record = MemoryRecordModel(
            user_id=body.user_id,
            kind=body.kind,
            content=body.content,
            tags=body.tags,
            metadata=body.metadata,
        )

        async with SessionLocal() as db:
            db.add(
                MemoryRecord(
                    id=record.id,
                    user_id=record.user_id,
                    kind=record.kind.value,
                    content=record.content,
                    tags=record.tags,
                    metadata_=record.metadata,
                    score=0.0,
                )
            )
            await db.commit()

        return record.model_dump(mode="json")

    async def query(self, body: MemoryQuery) -> list[dict[str, Any]]:
        async with SessionLocal() as db:
            stmt = select(MemoryRecord).limit(body.limit)
            if body.kind:
                stmt = stmt.where(MemoryRecord.kind == body.kind.value)
            if body.user_id:
                stmt = stmt.where(MemoryRecord.user_id == body.user_id)

            rows = (await db.execute(stmt)).scalars().all()
            q = body.query.lower()

            results = []
            for row in rows:
                score = 0.0
                if q in row.content.lower():
                    score += 1.0
                if any(q in tag.lower() for tag in row.tags or []):
                    score += 0.5

                if score > 0 or not q:
                    results.append(
                        {
                            "id": row.id,
                            "kind": row.kind,
                            "content": row.content,
                            "tags": row.tags,
                            "metadata": row.metadata_,
                            "score": score,
                        }
                    )

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[: body.limit]

    async def handle_memory_events(self, envelope: dict[str, Any]) -> None:
        if envelope.get("type") != "memory.write":
            return

        payload = MemoryWrite.model_validate(envelope["payload"])
        await self.write(payload)
