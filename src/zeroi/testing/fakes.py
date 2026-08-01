from typing import Any


class FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, Any]] = []

    async def publish(self, stream: str, event_type: str, payload: Any) -> str:
        self.published.append((stream, event_type, payload))
        return "evt_fake"

    async def emit_telemetry(self, level: str, message: str, **attributes: Any) -> None:
        self.published.append(("zeroi.telemetry", "telemetry.log", {"level": level, "message": message}))


class FakeService:
    def __init__(self) -> None:
        self.bus = FakeBus()
