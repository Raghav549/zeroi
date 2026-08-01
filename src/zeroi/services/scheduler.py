import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..bus import STREAM_EVENTS
from ..schemas import EventModel
from ..service import Service


async def scheduler_task(service: Service) -> None:
    scheduler = AsyncIOScheduler()

    async def tick():
        await service.bus.publish(
            STREAM_EVENTS,
            "event.structured",
            EventModel(
                source="scheduler",
                kind="tick",
                title="Scheduler tick",
                urgency="LOW",
            ),
        )

    scheduler.add_job(tick, "interval", seconds=60)
    scheduler.start()

    while True:
        await asyncio.sleep(3600)


def main() -> None:
    service = Service(name="scheduler", on_start=scheduler_task)
    service.run()


if __name__ == "__main__":
    main()
