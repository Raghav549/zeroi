from typing import Any

from sqlalchemy import select

from ..bus import STREAM_REQUESTS, EventBus
from ..db import SessionLocal
from ..models import AffairRecord
from ..schemas import Affair, EventModel, RequestCreated, utcnow


class EventProcessor:
    def __init__(self, bus: EventBus):
        self.bus = bus

    async def handle_event(self, envelope: dict[str, Any]) -> None:
        if envelope.get("type") != "event.structured":
            return

        event = EventModel.model_validate(envelope["payload"])
        affair = await self.associate_affair(event)
        proposal = self.reason_over_affair(affair, event)

        if proposal.get("auto_execute"):
            await self.bus.publish(
                STREAM_REQUESTS,
                "request.created",
                RequestCreated(
                    session_id=f"proactive_{affair.id}",
                    goal=proposal["goal"],
                    context={"affair_id": affair.id, "event_id": event.id, "proactive": True},
                ),
            )

    async def associate_affair(self, event: EventModel) -> Affair:
        kind = event.entities.get("affair_kind") or event.kind
        title = event.entities.get("affair_title") or event.title

        async with SessionLocal() as db:
            stmt = select(AffairRecord).where(AffairRecord.kind == kind).limit(1)
            row = (await db.execute(stmt)).scalar_one_or_none()

            if row:
                affair = Affair(
                    id=row.id,
                    kind=row.kind,
                    title=row.title,
                    state=row.state,
                    entities=row.entities,
                    deadlines=row.deadlines,
                    related_sessions=row.related_sessions,
                )
            else:
                affair = Affair(kind=kind, title=title)
                db.add(
                    AffairRecord(
                        id=affair.id,
                        kind=affair.kind,
                        title=affair.title,
                        state=affair.state,
                        entities=affair.entities,
                        deadlines=affair.deadlines,
                        related_sessions=affair.related_sessions,
                    )
                )

            affair.state["last_event"] = event.model_dump(mode="json")
            affair.updated_at = utcnow()

            if row:
                row.state = affair.state
                row.updated_at = affair.updated_at
            await db.commit()

        return affair

    def reason_over_affair(self, affair: Affair, event: EventModel) -> dict[str, Any]:
        urgency = event.urgency.value
        low_risk = event.kind in {"reminder", "calendar", "notification"}

        return {
            "affair_id": affair.id,
            "predicted_next_action": f"Prepare assistance for {affair.title}",
            "auto_execute": low_risk and urgency in {"LOW", "NORMAL"},
            "goal": f"Prepare context and next actions for affair: {affair.title}",
            "requires_confirmation": not low_risk,
        }
