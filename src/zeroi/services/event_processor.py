from typing import Any

from ..bus import STREAM_EVENTS
from ..events.processor import EventProcessor
from ..service import Service


def main() -> None:
    service = Service(name="event_processor")
    processor = EventProcessor(service.bus)

    async def handler(envelope: dict[str, Any]) -> None:
        await processor.handle_event(envelope)

    service.handlers = {STREAM_EVENTS: handler}
    service.run()


if __name__ == "__main__":
    main()
