from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..db import SessionLocal
from ..models import SessionRecord
from ..security import require_auth
from ..service import Service

router = APIRouter()


@router.get("/v1/sessions")
async def list_sessions(_=Depends(require_auth)):
    async with SessionLocal() as db:
        rows = (await db.execute(select(SessionRecord).limit(100))).scalars().all()
        return [
            {
                "id": r.id,
                "status": r.status,
                "goal": r.goal,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


@router.get("/v1/sessions/{session_id}")
async def get_session(session_id: str, _=Depends(require_auth)):
    async with SessionLocal() as db:
        row = await db.get(SessionRecord, session_id)
        if not row:
            raise HTTPException(404, "session not found")
        return {
            "id": row.id,
            "status": row.status,
            "goal": row.goal,
            "state": row.state,
        }


def main() -> None:
    service = Service(name="session_manager", router=router)
    service.run()


if __name__ == "__main__":
    main()
