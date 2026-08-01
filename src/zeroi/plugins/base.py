from typing import Any

from fastapi import APIRouter

from ..service import Service


class PluginAgent:
    """
    Base class for pluggable zeroi agents.

    A plugin agent owns:
    - a service name
    - an event stream
    - an optional HTTP router
    - an event handler

    The Harness core does not need to change to add a new agent.
    """

    name: str = "plugin_agent"
    stream: str = "zeroi.plugin"

    def __init__(self) -> None:
        self.router = APIRouter()

    async def handle(self, service: Service, envelope: dict[str, Any]) -> None:
        raise NotImplementedError

    def build_service(self) -> Service:
        service = Service(name=self.name, router=self.router)

        async def handler(envelope: dict[str, Any]) -> None:
            await self.handle(service, envelope)

        service.handlers = {self.stream: handler}
        return service
