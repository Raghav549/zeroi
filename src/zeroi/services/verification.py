from typing import Any

from ..bus import STREAM_TASKS, STREAM_VERIFY
from ..schemas import VerificationRequest
from ..service import Service
from ..verification.engine import VerificationEngine

engine = VerificationEngine()


async def handle_verify(service: Service, envelope: dict[str, Any]) -> None:
    if envelope.get("type") != "verification.requested":
        return

    request = VerificationRequest.model_validate(envelope["payload"])
    result = await engine.verify(request)
    await service.bus.publish(STREAM_TASKS, "verification.completed", result)


def main() -> None:
    service = Service(name="verification")

    async def handler(envelope: dict[str, Any]) -> None:
        await handle_verify(service, envelope)

    service.handlers = {STREAM_VERIFY: handler}
    service.run()


if __name__ == "__main__":
    main()
