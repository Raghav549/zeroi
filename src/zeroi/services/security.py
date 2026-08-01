from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..bus import STREAM_APPROVALS
from ..db import SessionLocal
from ..models import ApprovalRecord
from ..schemas import ApprovalDecided, ApprovalRequestModel
from ..security import require_auth
from ..service import Service

router = APIRouter()


class DecisionBody(BaseModel):
    approved: bool
    reason: str | None = None


def make_service() -> Service:
    service = Service(name="security", router=router)

    async def handle_approval_requests(envelope: dict[str, Any]) -> None:
        if envelope.get("type") != "approval.requested":
            return

        payload = ApprovalRequestModel.model_validate(envelope["payload"])

        async with SessionLocal() as db:
            existing = await db.get(ApprovalRecord, payload.id)
            if existing:
                return

            db.add(
                ApprovalRecord(
                    id=payload.id,
                    session_id=payload.session_id,
                    task_id=payload.task_id,
                    step_id=payload.step_id,
                    risk=payload.risk.value,
                    title=payload.title,
                    details=payload.details,
                    status="PENDING",
                )
            )
            await db.commit()

    @router.post("/v1/approvals/{approval_id}/decide")
    async def decide(approval_id: str, body: DecisionBody, _=Depends(require_auth)):
        async with SessionLocal() as db:
            record = await db.get(ApprovalRecord, approval_id)
            if not record:
                raise HTTPException(404, "approval not found")

            record.status = "APPROVED" if body.approved else "REJECTED"
            record.decided_at = datetime.now(timezone.utc)
            await db.commit()

        await service.bus.publish(
            STREAM_APPROVALS,
            "approval.decided",
            ApprovalDecided(id=approval_id, approved=body.approved, reason=body.reason),
        )
        return {"status": "ok"}

    service.handlers = {STREAM_APPROVALS: handle_approval_requests}
    return service


def main() -> None:
    service = make_service()
    service.run()


if __name__ == "__main__":
    main()
