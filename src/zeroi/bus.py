import asyncio
import json
import logging
import os
from typing import Any, Awaitable, Callable

import redis.asyncio as redis
from pydantic import BaseModel

from .config import settings
from .ids import new_id
from .schemas import Telemetry, utcnow

log = logging.getLogger(__name__)

STREAM_REQUESTS = "zeroi.requests"
STREAM_PLAN = "zeroi.plan"
STREAM_TASKS = "zeroi.tasks"
STREAM_GUI = "zeroi.gui"
STREAM_CLI = "zeroi.cli"
STREAM_BROWSER = "zeroi.browser"
STREAM_API = "zeroi.api"
STREAM_SEARCH = "zeroi.search"
STREAM_VERIFY = "zeroi.verify"
STREAM_MEMORY = "zeroi.memory"
STREAM_EVENTS = "zeroi.events"
STREAM_APPROVALS = "zeroi.approvals"
STREAM_TELEMETRY = "zeroi.telemetry"
STREAM_DLQ = "zeroi.dlq"

Handler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.consumer = f"{service_name}-{os.getpid()}"
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def publish(self, stream: str, event_type: str, payload: Any) -> str:
        if isinstance(payload, BaseModel):
            data = payload.model_dump(mode="json")
        else:
            data = payload

        envelope = {
            "id": new_id("evt"),
            "type": event_type,
            "ts": utcnow(),
            "producer": self.service_name,
            "payload": data,
        }
        await self.redis.xadd(stream, {"data": json.dumps(envelope, default=str)})
        return envelope["id"]

    async def emit_telemetry(self, level: str, message: str, **attributes: Any) -> None:
        try:
            await self.publish(
                STREAM_TELEMETRY,
                "telemetry.log",
                Telemetry(service=self.service_name, level=level, message=message, attributes=attributes),
            )
        except Exception:
            log.exception("failed emitting telemetry")

    async def ensure_group(self, stream: str) -> None:
        try:
            await self.redis.xgroup_create(stream, self.service_name, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def consume(self, stream: str, handler: Handler) -> None:
        await self.ensure_group(stream)
        log.info("consuming stream=%s group=%s", stream, self.service_name)

        while True:
            try:
                resp = await self.redis.xreadgroup(
                    groupname=self.service_name,
                    consumername=self.consumer,
                    streams={stream: ">"},
                    count=10,
                    block=5000,
                )
                if not resp:
                    continue

                for _, messages in resp:
                    for msg_id, fields in messages:
                        raw = fields.get("data", "{}")
                        try:
                            envelope = json.loads(raw)
                            await handler(envelope)
                        except Exception as exc:
                            log.exception("handler failed stream=%s msg=%s", stream, msg_id)
                            await self.publish(
                                STREAM_DLQ,
                                "dlq.message",
                                {
                                    "stream": stream,
                                    "error": str(exc),
                                    "envelope": json.loads(raw) if raw else None,
                                },
                            )
                        finally:
                            await self.redis.xack(stream, self.service_name, msg_id)
            except asyncio.CancelledError:
                log.info("consumer cancelled stream=%s", stream)
                break
            except Exception:
                log.exception("consumer error stream=%s", stream)
                await asyncio.sleep(1)
