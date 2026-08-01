from typing import Any

from ..bus import STREAM_TELEMETRY
from ..db import SessionLocal
from ..ids import new_id
from ..models import TelemetryRecord
from ..schemas import Telemetry
from ..service import Service


async def handle_telemetry(service: Service, envelope: dict[str, Any]) -> None:
    if envelope.get("type") != "telemetry.log":
        return

    payload = Telemetry.model_validate(envelope["payload"])

    async with SessionLocal() as db:
        db.add(
            TelemetryRecord(
                id=new_id("tel"),
                service=payload.service,
                level=payload.level,
                message=payload.message,
                attributes=payload.attributes,
            )
        )
        await db.commit()


def main() -> None:
    service = Service(name="logging_service")

    async def handler(envelope: dict[str, Any]) -> None:
        await handle_telemetry(service, envelope)

    service.handlers = {STREAM_TELEMETRY: handler}
    service.run()


if __name__ == "__main__":
    main()
