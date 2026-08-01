import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, Optional

import uvicorn
from fastapi import FastAPI
from prometheus_client import make_asgi_app

from .bus import EventBus
from .config import settings
from .db import init_db
from .logging import setup_logging

log = logging.getLogger(__name__)

StreamHandler = Callable[[dict], Awaitable[None]]
BackgroundTask = Callable[["Service"], Awaitable[None]]


class Service:
    def __init__(
        self,
        name: str,
        handlers: Optional[dict[str, StreamHandler]] = None,
        router=None,
        on_start: Optional[BackgroundTask] = None,
    ):
        self.name = name
        self.bus = EventBus(name)
        self.handlers = handlers or {}
        self.on_start = on_start

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            setup_logging(name)
            if settings.env != "prod":
                await init_db()

            tasks: list[asyncio.Task] = []

            for stream, handler in self.handlers.items():
                tasks.append(asyncio.create_task(self.bus.consume(stream, handler)))

            if self.on_start:
                tasks.append(asyncio.create_task(self.on_start(self)))

            await self.bus.emit_telemetry("INFO", "service_started", service=name)
            yield

            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)

        self.app = FastAPI(title=f"zeroi-{name}", lifespan=lifespan)
        self.app.mount("/metrics", make_asgi_app())

        @self.app.get("/healthz")
        async def healthz():
            return {"service": name, "status": "ok"}

        if router:
            self.app.include_router(router)

    def run(self, port: int = 8000) -> None:
        uvicorn.run(self.app, host="0.0.0.0", port=port)
