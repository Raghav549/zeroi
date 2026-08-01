from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..bus import STREAM_EVENTS
from ..schemas import EventModel, EventUrgency
from ..security import require_auth
from ..service import Service

router = APIRouter()


class NotificationIn(BaseModel):
    source: str
    title: str
    body: str | None = None
    raw: dict[str, Any] = {}


def parse_notification(notification: NotificationIn) -> EventModel:
    urgency = EventUrgency.NORMAL
    text = f"{notification.title} {notification.body or ''}".lower()

    if any(k in text for k in ["urgent", "asap", "critical"]):
        urgency = EventUrgency.HIGH
    if any(k in text for k in ["payment", "security", "fraud"]):
        urgency = EventUrgency.CRITICAL

    entities = {}
    if "flight" in text:
        entities["affair_kind"] = "travel"
    if "meeting" in text:
        entities["affair_kind"] = "meeting"
    if "order" in text or "purchase" in text:
        entities["affair_kind"] = "purchase"

    return EventModel(
        source=notification.source,
        kind="notification",
        title=notification.title,
        body=notification.body,
        urgency=urgency,
        entities=entities,
        raw=notification.raw,
    )


def make_service() -> Service:
    service = Service(name="notification_processor", router=router)

    @router.post("/v1/notifications")
    async def ingest_notification(body: NotificationIn, _=Depends(require_auth)):
        event = parse_notification(body)
        await service.bus.publish(STREAM_EVENTS, "event.structured", event)
        return {"event_id": event.id}

    return service


def main() -> None:
    service = make_service()
    service.run()


if __name__ == "__main__":
    main()
